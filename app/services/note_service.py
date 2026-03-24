import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import VAULT_DIR
from app.database import get_db
from app.services.link_parser import slugify, extract_links, extract_tags, parse_frontmatter


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def list_notes() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT n.id, n.title, n.updated_at,
                   (SELECT COUNT(*) FROM links WHERE source_id = n.id) as link_count
            FROM notes n ORDER BY n.updated_at DESC
        """).fetchall()
        result = []
        for r in rows:
            tags = [t['tag'] for t in conn.execute(
                "SELECT tag FROM tags WHERE note_id = ?", (r['id'],)
            ).fetchall()]
            result.append({
                "id": r['id'],
                "title": r['title'],
                "tags": tags,
                "link_count": r['link_count'],
                "updated_at": r['updated_at'],
            })
        return result


def get_note(note_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not row:
            return None

        tags = [t['tag'] for t in conn.execute(
            "SELECT tag FROM tags WHERE note_id = ?", (note_id,)
        ).fetchall()]

        links = [dict(r) for r in conn.execute(
            "SELECT target_id, context FROM links WHERE source_id = ?", (note_id,)
        ).fetchall()]

        backlinks = [dict(r) for r in conn.execute("""
            SELECT l.source_id, l.context, n.title as source_title
            FROM links l LEFT JOIN notes n ON n.id = l.source_id
            WHERE l.target_id = ?
        """, (note_id,)).fetchall()]

        return {
            "id": row['id'],
            "title": row['title'],
            "content": row['content'],
            "tags": tags,
            "links": links,
            "backlinks": backlinks,
            "created_at": row['created_at'],
            "updated_at": row['updated_at'],
        }


def create_note(title: str, content: str = "", tags: list[str] | None = None) -> dict:
    note_id = slugify(title)
    filepath = f"{note_id}.md"
    now = _now()

    # Write markdown file
    full_path = VAULT_DIR / filepath
    _write_md(full_path, title, content, tags or [])

    with get_db() as conn:
        conn.execute("""
            INSERT INTO notes (id, title, filepath, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note_id, title, filepath, content, now, now))

        _sync_links_tags(conn, note_id, content, tags or [])

    return get_note(note_id)


def update_note(note_id: str, title: str | None = None, content: str | None = None,
                tags: list[str] | None = None) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not row:
            return None

        new_title = title if title is not None else row['title']
        new_content = content if content is not None else row['content']
        now = _now()

        if tags is None:
            tags = extract_tags(new_content)
            existing_tags = [t['tag'] for t in conn.execute(
                "SELECT tag FROM tags WHERE note_id = ?", (note_id,)
            ).fetchall()]
            tags = list(set(tags + existing_tags))

        # Write file
        full_path = VAULT_DIR / row['filepath']
        _write_md(full_path, new_title, new_content, tags)

        conn.execute("""
            UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?
        """, (new_title, new_content, now, note_id))

        _sync_links_tags(conn, note_id, new_content, tags)

    return get_note(note_id)


def delete_note(note_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT filepath FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not row:
            return False

        full_path = VAULT_DIR / row['filepath']
        if full_path.exists():
            full_path.unlink()

        conn.execute("DELETE FROM links WHERE source_id = ?", (note_id,))
        conn.execute("DELETE FROM tags WHERE note_id = ?", (note_id,))
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return True


def scan_vault():
    with get_db() as conn:
        existing = {r['filepath'] for r in conn.execute("SELECT filepath FROM notes").fetchall()}
        found = set()

        for md_file in VAULT_DIR.glob("*.md"):
            filepath = md_file.name
            found.add(filepath)
            note_id = md_file.stem

            raw = md_file.read_text(encoding='utf-8')
            meta, body = parse_frontmatter(raw)
            title = meta.get('title', note_id.replace('-', ' ').title())
            content = body.strip()
            tags_from_meta = meta.get('tags', [])
            if isinstance(tags_from_meta, str):
                tags_from_meta = [t.strip() for t in tags_from_meta.split(',')]
            tags_from_content = extract_tags(content)
            all_tags = list(set(tags_from_meta + tags_from_content))

            mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            if filepath in existing:
                conn.execute("""
                    UPDATE notes SET title=?, content=?, updated_at=? WHERE filepath=?
                """, (title, content, mtime, filepath))
            else:
                now = _now()
                conn.execute("""
                    INSERT INTO notes (id, title, filepath, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (note_id, title, filepath, content, now, mtime))

            _sync_links_tags(conn, note_id, content, all_tags)

        # Remove notes whose files were deleted
        for fp in existing - found:
            nid = Path(fp).stem
            conn.execute("DELETE FROM links WHERE source_id = ?", (nid,))
            conn.execute("DELETE FROM tags WHERE note_id = ?", (nid,))
            conn.execute("DELETE FROM notes WHERE filepath = ?", (fp,))


def _sync_links_tags(conn, note_id: str, content: str, tags: list[str]):
    conn.execute("DELETE FROM links WHERE source_id = ?", (note_id,))
    links = extract_links(content)
    for link in links:
        conn.execute(
            "INSERT OR REPLACE INTO links (source_id, target_id, context) VALUES (?, ?, ?)",
            (note_id, link['target'], link['context'])
        )

    conn.execute("DELETE FROM tags WHERE note_id = ?", (note_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR REPLACE INTO tags (note_id, tag) VALUES (?, ?)",
            (note_id, tag.lower())
        )


def _write_md(path: Path, title: str, content: str, tags: list[str]):
    lines = ["---"]
    lines.append(f"title: {title}")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    lines.append("")
    lines.append(content)
    path.write_text('\n'.join(lines), encoding='utf-8')
