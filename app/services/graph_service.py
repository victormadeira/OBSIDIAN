from app.database import get_db


def get_full_graph() -> dict:
    with get_db() as conn:
        notes = conn.execute("""
            SELECT n.id, n.title,
                (SELECT COUNT(*) FROM links WHERE source_id = n.id) as out_links,
                (SELECT COUNT(*) FROM links WHERE target_id = n.id) as in_links,
                (SELECT COUNT(*) FROM links WHERE source_id = n.id) +
                (SELECT COUNT(*) FROM links WHERE target_id = n.id) as link_count
            FROM notes n
        """).fetchall()

        # Tags per note
        tags_map = {}
        for row in conn.execute("SELECT note_id, tag FROM tags"):
            tags_map.setdefault(row['note_id'], []).append(row['tag'])

        # Semantic clusters
        cluster_map = _build_cluster_map(conn, tags_map)

        # Link types
        link_types = {}
        for row in conn.execute("SELECT source_id, target_id, rel_type FROM link_types"):
            link_types[(row['source_id'], row['target_id'])] = row['rel_type']

        nodes = []
        node_ids = set()
        for n in notes:
            node_ids.add(n['id'])
            nodes.append({
                "id": n['id'],
                "title": n['title'],
                "link_count": n['link_count'],
                "in_links": n['in_links'],
                "out_links": n['out_links'],
                "tags": tags_map.get(n['id'], []),
                "cluster": cluster_map.get(n['id'], -1),
            })

        edges_raw = conn.execute("""
            SELECT l.source_id, l.target_id, l.context
            FROM links l
        """).fetchall()
        edges = []
        for e in edges_raw:
            sid, tid = e['source_id'], e['target_id']
            # Phantom nodes
            if tid not in node_ids:
                node_ids.add(tid)
                nodes.append({
                    "id": tid,
                    "title": tid.replace('-', ' ').title(),
                    "link_count": 1, "in_links": 1, "out_links": 0,
                    "tags": [],
                    "phantom": True,
                    "cluster": -1,
                })
            # Check if bidirectional
            is_bidirectional = any(
                x['source_id'] == tid and x['target_id'] == sid for x in edges_raw
            )
            edges.append({
                "source": sid,
                "target": tid,
                "rel_type": link_types.get((sid, tid), "references"),
                "bidirectional": is_bidirectional,
                "context": e['context'] or "",
            })

        # Compute clusters summary
        cluster_labels = _build_cluster_labels(cluster_map, tags_map)

    return {"nodes": nodes, "edges": edges, "clusters": cluster_labels}


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
                for r in conn.execute("SELECT target_id FROM links WHERE source_id = ?", (nid,)):
                    if r['target_id'] not in visited:
                        next_visit.add(r['target_id'])
                for r in conn.execute("SELECT source_id FROM links WHERE target_id = ?", (nid,)):
                    if r['source_id'] not in visited:
                        next_visit.add(r['source_id'])
            to_visit = next_visit

        tags_map = {}
        for row in conn.execute("SELECT note_id, tag FROM tags"):
            tags_map.setdefault(row['note_id'], []).append(row['tag'])

        cluster_map = _build_cluster_map(conn, tags_map)

        nodes = []
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
                    "cluster": cluster_map.get(nid, -1),
                    "is_center": nid == note_id,
                })
            else:
                nodes.append({
                    "id": nid, "title": nid.replace('-', ' ').title(),
                    "link_count": 1, "tags": [], "phantom": True, "cluster": -1,
                })

        edges = []
        for nid in visited:
            if not visited:
                continue
            placeholders = ','.join('?' * len(visited))
            rows = conn.execute(
                f"SELECT source_id, target_id FROM links WHERE source_id = ? AND target_id IN ({placeholders})",
                (nid, *visited)
            ).fetchall()
            for r in rows:
                edges.append({"source": r['source_id'], "target": r['target_id']})

    return {"nodes": nodes, "edges": edges}


def _build_cluster_map(conn, tags_map: dict) -> dict:
    """Assign each note to a cluster based on primary tag group."""
    # Group notes by their most common shared tag
    tag_groups = {}
    for nid, tags in tags_map.items():
        if tags:
            primary = tags[0]  # Use first tag as primary cluster
            tag_groups.setdefault(primary, []).append(nid)

    cluster_map = {}
    for idx, (tag, nids) in enumerate(tag_groups.items()):
        for nid in nids:
            cluster_map[nid] = idx

    return cluster_map


def _build_cluster_labels(cluster_map: dict, tags_map: dict) -> list[dict]:
    """Build cluster metadata for the frontend."""
    clusters = {}
    for nid, cid in cluster_map.items():
        clusters.setdefault(cid, []).append(nid)

    result = []
    for cid, members in clusters.items():
        # Find shared tags
        all_tags = set()
        for m in members:
            all_tags.update(tags_map.get(m, []))
        result.append({
            "id": cid,
            "label": ", ".join(sorted(all_tags)[:3]),
            "size": len(members),
            "node_ids": members,
        })
    return result
