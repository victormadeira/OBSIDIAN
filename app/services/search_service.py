from app.database import get_db


def search_notes(query: str, limit: int = 20) -> list[dict]:
    if not query or not query.strip():
        return []

    # Prepare query for FTS5
    terms = query.strip().split()
    fts_query = ' '.join(f'"{t}"*' for t in terms)

    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                notes_fts.id,
                notes_fts.title,
                snippet(notes_fts, 2, '<mark>', '</mark>', '...', 40) as snippet,
                bm25(notes_fts) as rank
            FROM notes_fts
            WHERE notes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()

        return [{"id": r['id'], "title": r['title'], "snippet": r['snippet'], "rank": r['rank']}
                for r in rows]
