from app.database import get_db


def get_full_graph() -> dict:
    with get_db() as conn:
        notes = conn.execute("""
            SELECT n.id, n.title,
                (SELECT COUNT(*) FROM links WHERE source_id = n.id) +
                (SELECT COUNT(*) FROM links WHERE target_id = n.id) as link_count
            FROM notes n
        """).fetchall()

        # Get tags per note for coloring
        tags_map = {}
        for row in conn.execute("SELECT note_id, tag FROM tags"):
            tags_map.setdefault(row['note_id'], []).append(row['tag'])

        nodes = []
        node_ids = set()
        for n in notes:
            node_ids.add(n['id'])
            nodes.append({
                "id": n['id'],
                "title": n['title'],
                "link_count": n['link_count'],
                "tags": tags_map.get(n['id'], []),
            })

        edges_raw = conn.execute("SELECT source_id, target_id FROM links").fetchall()
        edges = []
        for e in edges_raw:
            # Add phantom nodes for links to non-existent notes
            if e['target_id'] not in node_ids:
                node_ids.add(e['target_id'])
                nodes.append({
                    "id": e['target_id'],
                    "title": e['target_id'].replace('-', ' ').title(),
                    "link_count": 1,
                    "tags": [],
                    "phantom": True,
                })
            edges.append({"source": e['source_id'], "target": e['target_id']})

    return {"nodes": nodes, "edges": edges}


def get_ego_graph(note_id: str, depth: int = 1) -> dict:
    with get_db() as conn:
        visited = set()
        to_visit = {note_id}

        for _ in range(depth + 1):
            if not to_visit:
                break
            visited.update(to_visit)
            next_visit = set()
            for nid in to_visit:
                rows = conn.execute(
                    "SELECT target_id FROM links WHERE source_id = ?", (nid,)
                ).fetchall()
                for r in rows:
                    if r['target_id'] not in visited:
                        next_visit.add(r['target_id'])
                rows = conn.execute(
                    "SELECT source_id FROM links WHERE target_id = ?", (nid,)
                ).fetchall()
                for r in rows:
                    if r['source_id'] not in visited:
                        next_visit.add(r['source_id'])
            to_visit = next_visit

        nodes = []
        tags_map = {}
        for row in conn.execute("SELECT note_id, tag FROM tags"):
            tags_map.setdefault(row['note_id'], []).append(row['tag'])

        for nid in visited:
            row = conn.execute("SELECT id, title FROM notes WHERE id = ?", (nid,)).fetchone()
            if row:
                lc = conn.execute(
                    "SELECT COUNT(*) as c FROM links WHERE source_id = ? OR target_id = ?",
                    (nid, nid)
                ).fetchone()['c']
                nodes.append({
                    "id": row['id'], "title": row['title'],
                    "link_count": lc, "tags": tags_map.get(nid, []),
                })
            else:
                nodes.append({
                    "id": nid, "title": nid.replace('-', ' ').title(),
                    "link_count": 1, "tags": [], "phantom": True,
                })

        edges = []
        for nid in visited:
            rows = conn.execute(
                "SELECT source_id, target_id FROM links WHERE source_id = ? AND target_id IN ({})".format(
                    ','.join('?' * len(visited))
                ), (nid, *visited)
            ).fetchall()
            for r in rows:
                edges.append({"source": r['source_id'], "target": r['target_id']})

    return {"nodes": nodes, "edges": edges}
