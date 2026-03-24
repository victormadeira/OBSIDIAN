"""
Vector API endpoints — semantic search, similarity, link suggestions, reindex.

These endpoints use the vector service (ChromaDB + embedding provider).
If the vector service is unavailable, they return graceful fallbacks.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services import vector_service

router = APIRouter(prefix="/api/vectors", tags=["vectors"])


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    tag_filter: Optional[str] = None


# ---- Status ----

@router.get("/status")
def vector_status():
    """Check if vector service is operational and get stats."""
    return vector_service.get_status()


# ---- Indexing ----

@router.post("/reindex")
def reindex():
    """
    Full reindex: rebuild ALL embeddings from SQLite.
    Safe to call anytime — ChromaDB is derived data, SQLite is source of truth.
    """
    if not vector_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Vector service not available. Check server logs for initialization errors."
        )
    return vector_service.reindex_all()


# ---- Semantic Search ----

@router.post("/search")
def semantic_search(req: SemanticSearchRequest):
    """
    Search notes by meaning, not just keywords.
    Uses embedding similarity instead of FTS5 keyword matching.
    """
    if not vector_service.is_available():
        return {"results": [], "fallback": "keyword", "message": "Vector service unavailable"}

    results = vector_service.semantic_search(
        query=req.query,
        limit=req.limit,
        tag_filter=req.tag_filter,
    )
    return {"results": results, "method": "semantic"}


@router.get("/search")
def semantic_search_get(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    tag: Optional[str] = None,
):
    """GET version of semantic search for easy browser/curl usage."""
    if not vector_service.is_available():
        return {"results": [], "fallback": "keyword", "message": "Vector service unavailable"}

    results = vector_service.semantic_search(query=q, limit=limit, tag_filter=tag)
    return {"results": results, "method": "semantic"}


# ---- Similarity ----

@router.get("/similar/{note_id}")
def similar_notes(note_id: str, limit: int = Query(10, ge=1, le=50)):
    """
    Find notes semantically similar to a given note.
    Uses actual embedding distance — much better than tag-based Jaccard.
    """
    if not vector_service.is_available():
        # Fallback to tag-based similarity
        from app.services.semantic_service import get_similarity_scores
        return {
            "results": get_similarity_scores(note_id)[:limit],
            "method": "tags_fallback",
        }

    results = vector_service.find_similar_notes(note_id, limit=limit)
    return {"results": results, "method": "semantic"}


# ---- Link Suggestions ----

@router.get("/suggest-links/{note_id}")
def suggest_links(
    note_id: str,
    limit: int = Query(5, ge=1, le=20),
    threshold: float = Query(0.3, ge=0.0, le=1.0),
):
    """
    Suggest notes that should be linked but aren't.
    Discovers hidden connections based on semantic similarity.
    """
    if not vector_service.is_available():
        raise HTTPException(status_code=503, detail="Vector service unavailable")

    suggestions = vector_service.suggest_links(note_id, limit=limit, threshold=threshold)
    return {"suggestions": suggestions}


# ---- Tag Suggestions ----

@router.get("/suggest-tags/{note_id}")
def suggest_tags(note_id: str, limit: int = Query(5, ge=1, le=20)):
    """
    Suggest tags for a note based on what semantically similar notes use.
    """
    if not vector_service.is_available():
        raise HTTPException(status_code=503, detail="Vector service unavailable")

    suggestions = vector_service.auto_suggest_tags(note_id, limit=limit)
    return {"suggestions": suggestions}


# ---- Embedding Clusters ----

@router.get("/clusters")
def embedding_clusters(n_clusters: int = Query(0, ge=0, le=50)):
    """
    Cluster notes based on embedding similarity.
    n_clusters=0 means auto-detect optimal number.
    """
    if not vector_service.is_available():
        raise HTTPException(status_code=503, detail="Vector service unavailable")

    clusters = vector_service.get_embedding_clusters(n_clusters=n_clusters)
    return {"clusters": clusters}
