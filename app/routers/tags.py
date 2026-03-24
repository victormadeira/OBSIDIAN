from fastapi import APIRouter
from app.database import get_db

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("")
def list_tags():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC
        """).fetchall()
        return [{"tag": r['tag'], "count": r['count']} for r in rows]


@router.get("/{tag}/notes")
def notes_by_tag(tag: str):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT n.id, n.title, n.updated_at
            FROM notes n JOIN tags t ON t.note_id = n.id
            WHERE t.tag = ? ORDER BY n.updated_at DESC
        """, (tag.lower(),)).fetchall()
        return [dict(r) for r in rows]
