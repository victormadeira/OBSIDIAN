from fastapi import APIRouter, Query
from app.services import semantic_service
from app.database import get_db

router = APIRouter(prefix="/api/semantic", tags=["semantic"])


@router.get("/similar/{note_id}")
def similar_notes(note_id: str):
    return semantic_service.get_similarity_scores(note_id)


@router.get("/clusters")
def clusters():
    return semantic_service.get_clusters()


@router.get("/cooccurrence")
def tag_cooccurrence():
    return semantic_service.get_tag_cooccurrence()


@router.get("/orphans")
def orphan_notes():
    return semantic_service.get_orphan_notes()


@router.get("/hubs")
def hub_notes(limit: int = Query(10, ge=1, le=50)):
    return semantic_service.get_hub_notes(limit)


@router.get("/stats/{note_id}")
def note_stats(note_id: str):
    stats = semantic_service.get_note_stats(note_id)
    if not stats:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Note not found")
    return stats


# Collections CRUD
@router.post("/collections")
def create_collection(data: dict):
    with get_db() as conn:
        from app.services.link_parser import slugify
        cid = slugify(data['name'])
        conn.execute(
            "INSERT INTO collections (id, name, description, color) VALUES (?, ?, ?, ?)",
            (cid, data['name'], data.get('description', ''), data.get('color', '#89b4fa'))
        )
        for nid in data.get('note_ids', []):
            conn.execute(
                "INSERT OR IGNORE INTO collection_notes (collection_id, note_id) VALUES (?, ?)",
                (cid, nid)
            )
    return {"id": cid, "name": data['name']}


@router.get("/collections")
def list_collections():
    with get_db() as conn:
        collections = conn.execute("SELECT * FROM collections ORDER BY created_at DESC").fetchall()
        result = []
        for c in collections:
            notes = conn.execute("""
                SELECT n.id, n.title FROM collection_notes cn
                JOIN notes n ON n.id = cn.note_id
                WHERE cn.collection_id = ?
            """, (c['id'],)).fetchall()
            result.append({
                "id": c['id'],
                "name": c['name'],
                "description": c['description'],
                "color": c['color'],
                "notes": [dict(n) for n in notes],
                "count": len(notes),
            })
        return result


@router.put("/collections/{collection_id}/notes")
def update_collection_notes(collection_id: str, data: dict):
    with get_db() as conn:
        conn.execute("DELETE FROM collection_notes WHERE collection_id = ?", (collection_id,))
        for nid in data.get('note_ids', []):
            conn.execute(
                "INSERT INTO collection_notes (collection_id, note_id) VALUES (?, ?)",
                (collection_id, nid)
            )
    return {"ok": True}


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM collection_notes WHERE collection_id = ?", (collection_id,))
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    return {"ok": True}


# Link types
@router.put("/link-type")
def set_link_type(data: dict):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO link_types (source_id, target_id, rel_type) VALUES (?, ?, ?)",
            (data['source_id'], data['target_id'], data.get('rel_type', 'references'))
        )
    return {"ok": True}


@router.get("/link-types")
def get_link_types():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM link_types").fetchall()
        return [dict(r) for r in rows]
