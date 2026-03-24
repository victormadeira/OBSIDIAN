"""
Vector Service — orchestrates embedding providers + ChromaDB storage.

This is the central service for all vector operations:
  - Index notes as embeddings in ChromaDB
  - Semantic search (query → embedding → cosine similarity → results)
  - Find truly similar notes (embedding distance, not just tag overlap)
  - Suggest missing links between semantically related notes
  - Auto-generate tag suggestions based on cluster proximity
  - Full reindex from SQLite source of truth

Architecture:
  SQLite = source of truth (notes, links, tags)
  ChromaDB = derived vector index (can be rebuilt from SQLite at any time)
  EmbeddingProvider = pluggable (local, openai, ollama)
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton state
_provider = None
_chroma_client = None
_collection = None
_initialized = False

COLLECTION_NAME = "obsidian_notes"


def init_vector_service(provider_type: str = "local", model_name: Optional[str] = None, **kwargs):
    """Initialize the vector service with the configured provider."""
    global _provider, _chroma_client, _collection, _initialized

    from app.services.embedding_provider import create_provider
    from app.config import VAULT_DIR

    try:
        # Create embedding provider
        _provider = create_provider(provider_type=provider_type, model_name=model_name, **kwargs)
        logger.info(f"Embedding provider: {_provider.get_model_name()}")

        # Create ChromaDB client (embedded, persistent on disk)
        import chromadb
        from chromadb.config import Settings

        chroma_path = str(VAULT_DIR / ".chroma_db")
        _chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create the notes collection
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine",
                "model": _provider.get_model_name(),
            },
        )

        _initialized = True
        logger.info(
            f"Vector service initialized. "
            f"ChromaDB at: {chroma_path} | "
            f"Collection: {COLLECTION_NAME} ({_collection.count()} vectors)"
        )
        return True

    except Exception as e:
        logger.warning(f"Vector service initialization failed: {e}")
        logger.warning("Semantic search will be unavailable. System continues with keyword search.")
        _initialized = False
        return False


def is_available() -> bool:
    """Check if vector service is operational."""
    return _initialized and _provider is not None and _collection is not None


def get_status() -> dict:
    """Return current status of the vector service."""
    if not is_available():
        return {
            "status": "unavailable",
            "provider": None,
            "indexed_count": 0,
            "dimension": None,
        }
    return {
        "status": "ready",
        "provider": _provider.get_model_name(),
        "indexed_count": _collection.count(),
        "dimension": _provider.get_dimension(),
    }


def _prepare_note_text(title: str, content: str, tags: list[str]) -> str:
    """Combine note fields into a single text for embedding."""
    parts = [f"# {title}"]
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    if content:
        # Truncate very long content to keep embedding focused
        max_chars = 8000
        text = content[:max_chars]
        if len(content) > max_chars:
            text += "..."
        parts.append(text)
    return "\n\n".join(parts)


def index_note(note_id: str, title: str, content: str, tags: list[str]):
    """Index or update a single note's embedding."""
    if not is_available():
        return

    text = _prepare_note_text(title, content, tags)
    embedding = _provider.embed_text(text)

    _collection.upsert(
        ids=[note_id],
        embeddings=[embedding],
        metadatas=[{
            "title": title,
            "tags": ",".join(tags) if tags else "",
            "word_count": len(content.split()) if content else 0,
        }],
        documents=[text],
    )


def remove_note(note_id: str):
    """Remove a note from the vector index."""
    if not is_available():
        return
    try:
        _collection.delete(ids=[note_id])
    except Exception:
        pass  # Note might not be indexed


def reindex_all() -> dict:
    """
    Full reindex: rebuild all embeddings from SQLite source of truth.
    This is safe — ChromaDB is derived data.
    """
    if not is_available():
        return {"status": "unavailable", "indexed": 0, "duration_ms": 0}

    from app.database import get_db

    start = time.time()

    # Clear existing collection
    global _collection
    _chroma_client.delete_collection(COLLECTION_NAME)
    _collection = _chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "model": _provider.get_model_name(),
        },
    )

    # Fetch all notes from SQLite
    with get_db() as conn:
        notes = conn.execute("SELECT id, title, content FROM notes").fetchall()
        note_tags = {}
        for row in conn.execute("SELECT note_id, tag FROM tags"):
            note_tags.setdefault(row["note_id"], []).append(row["tag"])

    if not notes:
        return {"status": "ok", "indexed": 0, "duration_ms": 0}

    # Prepare texts
    ids = []
    texts = []
    metadatas = []
    for note in notes:
        nid = note["id"]
        tags = note_tags.get(nid, [])
        text = _prepare_note_text(note["title"], note["content"], tags)
        ids.append(nid)
        texts.append(text)
        metadatas.append({
            "title": note["title"],
            "tags": ",".join(tags),
            "word_count": len(note["content"].split()) if note["content"] else 0,
        })

    # Batch embed
    logger.info(f"Generating embeddings for {len(texts)} notes...")
    embeddings = _provider.embed_batch(texts)

    # Batch insert into ChromaDB
    BATCH = 500
    for i in range(0, len(ids), BATCH):
        _collection.add(
            ids=ids[i:i + BATCH],
            embeddings=embeddings[i:i + BATCH],
            metadatas=metadatas[i:i + BATCH],
            documents=texts[i:i + BATCH],
        )

    duration_ms = int((time.time() - start) * 1000)
    logger.info(f"Reindex complete: {len(ids)} notes in {duration_ms}ms")

    return {
        "status": "ok",
        "indexed": len(ids),
        "duration_ms": duration_ms,
        "model": _provider.get_model_name(),
    }


def semantic_search(query: str, limit: int = 10, tag_filter: Optional[str] = None) -> list[dict]:
    """
    Search notes by semantic meaning, not just keywords.
    Query is embedded and compared via cosine similarity in ChromaDB.
    """
    if not is_available():
        return []

    query_embedding = _provider.embed_text(query)

    where_filter = None
    if tag_filter:
        where_filter = {"tags": {"$contains": tag_filter}}

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit, _collection.count() or 1),
        where=where_filter,
        include=["metadatas", "distances", "documents"],
    )

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    output = []
    for i, nid in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 1.0
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity score: 1 = identical, 0 = orthogonal
        similarity = max(0, 1 - distance)

        output.append({
            "id": nid,
            "title": meta.get("title", ""),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "similarity": round(similarity, 4),
            "word_count": meta.get("word_count", 0),
        })

    return output


def find_similar_notes(note_id: str, limit: int = 10) -> list[dict]:
    """
    Find notes semantically similar to a given note using vector distance.
    This is the REAL similarity — based on meaning, not just shared tags.
    """
    if not is_available():
        return []

    # Get the note's embedding from ChromaDB
    try:
        result = _collection.get(ids=[note_id], include=["embeddings"])
        if not result or not result["embeddings"] or not result["embeddings"][0]:
            return []
        note_embedding = result["embeddings"][0]
    except Exception:
        return []

    # Query similar (limit+1 because the note itself will be in results)
    results = _collection.query(
        query_embeddings=[note_embedding],
        n_results=min(limit + 1, _collection.count() or 1),
        include=["metadatas", "distances"],
    )

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    output = []
    for i, nid in enumerate(results["ids"][0]):
        if nid == note_id:
            continue  # Skip self
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 1.0
        similarity = max(0, 1 - distance)

        output.append({
            "id": nid,
            "title": meta.get("title", ""),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "similarity": round(similarity, 4),
        })

    return output[:limit]


def suggest_links(note_id: str, limit: int = 5, threshold: float = 0.3) -> list[dict]:
    """
    Suggest notes that SHOULD be linked but aren't.
    Finds semantically similar notes that don't have an explicit [[link]].
    This is the killer feature — discovering connections you missed.
    """
    if not is_available():
        return []

    from app.database import get_db

    # Get existing links for this note
    with get_db() as conn:
        existing_links = set()
        for row in conn.execute("SELECT target_id FROM links WHERE source_id = ?", (note_id,)):
            existing_links.add(row["target_id"])
        for row in conn.execute("SELECT source_id FROM links WHERE target_id = ?", (note_id,)):
            existing_links.add(row["source_id"])

    # Get semantically similar notes
    similar = find_similar_notes(note_id, limit=limit + len(existing_links))

    # Filter: only notes that are similar but NOT already linked
    suggestions = []
    for note in similar:
        if note["id"] not in existing_links and note["similarity"] >= threshold:
            suggestions.append({
                "id": note["id"],
                "title": note["title"],
                "similarity": note["similarity"],
                "reason": f"Semanticamente similar ({int(note['similarity'] * 100)}%) mas sem link direto",
            })

    return suggestions[:limit]


def auto_suggest_tags(note_id: str, limit: int = 5) -> list[dict]:
    """
    Suggest tags for a note based on what similar notes use.
    Looks at the tags of semantically similar notes and suggests
    tags this note doesn't have yet.
    """
    if not is_available():
        return []

    from app.database import get_db

    # Get this note's current tags
    with get_db() as conn:
        current_tags = {r["tag"] for r in conn.execute(
            "SELECT tag FROM tags WHERE note_id = ?", (note_id,)
        ).fetchall()}

    # Get similar notes
    similar = find_similar_notes(note_id, limit=20)

    # Count tags across similar notes (weighted by similarity)
    tag_scores = {}
    for note in similar:
        weight = note["similarity"]
        for tag in note["tags"]:
            if tag and tag not in current_tags:
                tag_scores[tag] = tag_scores.get(tag, 0) + weight

    # Sort by score
    sorted_tags = sorted(tag_scores.items(), key=lambda x: -x[1])

    return [
        {"tag": tag, "confidence": round(score, 3)}
        for tag, score in sorted_tags[:limit]
    ]


def get_embedding_clusters(n_clusters: int = 0) -> list[dict]:
    """
    Cluster notes using actual embedding similarity (not just tags).
    Uses simple agglomerative clustering on the embedding space.
    If n_clusters=0, auto-detect optimal number.
    """
    if not is_available() or _collection.count() < 3:
        return []

    try:
        # Get all embeddings
        all_data = _collection.get(include=["embeddings", "metadatas"])
        if not all_data or not all_data["embeddings"]:
            return []

        import numpy as np
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import silhouette_score

        ids = all_data["ids"]
        embeddings = np.array(all_data["embeddings"])
        metadatas = all_data["metadatas"]

        n_notes = len(ids)
        if n_notes < 3:
            return []

        # Auto-detect number of clusters
        if n_clusters <= 0:
            best_k = 2
            best_score = -1
            max_k = min(n_notes - 1, 10)
            for k in range(2, max_k + 1):
                clustering = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
                labels = clustering.fit_predict(embeddings)
                if len(set(labels)) < 2:
                    continue
                score = silhouette_score(embeddings, labels, metric="cosine")
                if score > best_score:
                    best_score = score
                    best_k = k
            n_clusters = best_k

        clustering = AgglomerativeClustering(n_clusters=n_clusters, metric="cosine", linkage="average")
        labels = clustering.fit_predict(embeddings)

        # Group results
        clusters = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = []
            meta = metadatas[i] if metadatas else {}
            clusters[label].append({
                "id": ids[i],
                "title": meta.get("title", ""),
                "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            })

        return [
            {
                "cluster_id": cid,
                "notes": notes,
                "size": len(notes),
            }
            for cid, notes in sorted(clusters.items())
        ]

    except ImportError:
        logger.warning("sklearn not available — embedding clustering disabled")
        return []
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        return []
