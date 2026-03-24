import json
from datetime import datetime, timezone
from app.database import get_db
from app.services.note_service import get_note


def build_context(note_ids: list[str], include_linked: bool = True, depth: int = 1,
                  fmt: str = "xml", max_tokens: int = 8000, include_metadata: bool = True) -> dict:
    # Collect all note IDs to include
    all_ids = set(note_ids)

    if include_linked:
        with get_db() as conn:
            for _ in range(depth):
                new_ids = set()
                for nid in list(all_ids):
                    rows = conn.execute(
                        "SELECT target_id FROM links WHERE source_id = ?", (nid,)
                    ).fetchall()
                    for r in rows:
                        new_ids.add(r['target_id'])
                    rows = conn.execute(
                        "SELECT source_id FROM links WHERE target_id = ?", (nid,)
                    ).fetchall()
                    for r in rows:
                        new_ids.add(r['source_id'])
                all_ids.update(new_ids)

    # Load notes
    notes = []
    for nid in all_ids:
        note = get_note(nid)
        if note:
            notes.append(note)

    # Sort: requested notes first, then by link count descending
    requested_set = set(note_ids)
    notes.sort(key=lambda n: (0 if n['id'] in requested_set else 1, -len(n.get('links', []))))

    # Token budget trimming (rough: 1 token ~= 4 chars)
    char_budget = max_tokens * 4
    included_notes = []
    total_chars = 0
    for note in notes:
        note_chars = len(note['content']) + len(note['title']) + 100  # overhead
        if total_chars + note_chars > char_budget and note['id'] not in requested_set:
            continue
        included_notes.append(note)
        total_chars += note_chars

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    estimated_tokens = total_chars // 4

    if fmt == "xml":
        content = _format_xml(included_notes, note_ids, now, include_metadata)
    elif fmt == "json":
        content = _format_json(included_notes, note_ids, now, include_metadata)
    else:
        content = _format_markdown(included_notes, note_ids, now, include_metadata)

    return {
        "content": content,
        "format": fmt,
        "note_count": len(included_notes),
        "estimated_tokens": estimated_tokens,
    }


def _format_xml(notes: list[dict], requested: list[str], timestamp: str, metadata: bool) -> str:
    lines = [f'<knowledge-base query="{", ".join(requested)}" generated="{timestamp}" notes="{len(notes)}">']

    for note in notes:
        tags_str = ", ".join(note.get('tags', []))
        attrs = f'id="{note["id"]}" title="{_xml_escape(note["title"])}"'
        if metadata:
            attrs += f' tags="{_xml_escape(tags_str)}" updated="{note.get("updated_at", "")}"'
        lines.append(f'  <note {attrs}>')
        lines.append(f'    <content>')
        lines.append(f'      {_xml_escape(note["content"])}')
        lines.append(f'    </content>')

        if metadata and note.get('links'):
            lines.append(f'    <links>')
            for link in note['links']:
                ctx = _xml_escape(link.get('context', ''))
                lines.append(f'      <link target="{link["target_id"]}" context="{ctx}"/>')
            lines.append(f'    </links>')

        if metadata and note.get('backlinks'):
            lines.append(f'    <backlinks>')
            for bl in note['backlinks']:
                lines.append(f'      <backlink source="{bl["source_id"]}" title="{_xml_escape(bl.get("source_title", ""))}"/>')
            lines.append(f'    </backlinks>')

        lines.append(f'  </note>')

    # Graph summary
    all_tags = set()
    total_links = 0
    for n in notes:
        all_tags.update(n.get('tags', []))
        total_links += len(n.get('links', []))
    lines.append(f'  <graph-summary notes="{len(notes)}" links="{total_links}" tags="{", ".join(sorted(all_tags))}"/>')
    lines.append('</knowledge-base>')
    return '\n'.join(lines)


def _format_markdown(notes: list[dict], requested: list[str], timestamp: str, metadata: bool) -> str:
    lines = [f'# Knowledge Base Context', f'> Generated: {timestamp} | Notes: {len(notes)}', '']

    for note in notes:
        lines.append(f'## {note["title"]}')
        if metadata:
            tags = ', '.join(f'`{t}`' for t in note.get('tags', []))
            lines.append(f'**Tags:** {tags} | **Updated:** {note.get("updated_at", "")}')
            lines.append('')
        lines.append(note['content'])
        lines.append('')

        if metadata and note.get('links'):
            lines.append('**Links:**')
            for link in note['links']:
                lines.append(f'- → [[{link["target_id"]}]]: {link.get("context", "")}')
            lines.append('')

        if metadata and note.get('backlinks'):
            lines.append('**Backlinks:**')
            for bl in note['backlinks']:
                lines.append(f'- ← [[{bl["source_id"]}]] ({bl.get("source_title", "")})')
            lines.append('')

        lines.append('---')
        lines.append('')

    return '\n'.join(lines)


def _format_json(notes: list[dict], requested: list[str], timestamp: str, metadata: bool) -> str:
    data = {
        "knowledge_base": {
            "query": requested,
            "generated": timestamp,
            "note_count": len(notes),
            "notes": [],
        }
    }
    for note in notes:
        entry = {"id": note['id'], "title": note['title'], "content": note['content']}
        if metadata:
            entry["tags"] = note.get('tags', [])
            entry["updated_at"] = note.get('updated_at', '')
            entry["links"] = [{"target": l['target_id'], "context": l.get('context', '')} for l in note.get('links', [])]
            entry["backlinks"] = [{"source": bl['source_id'], "title": bl.get('source_title', '')} for bl in note.get('backlinks', [])]
        data["knowledge_base"]["notes"].append(entry)
    return json.dumps(data, indent=2, ensure_ascii=False)


def _xml_escape(text: str) -> str:
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
