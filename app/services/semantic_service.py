"""Semantic analysis service: similarity, clustering, co-occurrence, recommendations."""
from app.database import get_db


def get_similarity_scores(note_id: str) -> list[dict]:
    """Find similar notes based on shared tags + shared link targets."""
    with get_db() as conn:
        # Get this note's tags and link targets
        my_tags = {r['tag'] for r in conn.execute(
            "SELECT tag FROM tags WHERE note_id = ?", (note_id,)
        ).fetchall()}

        my_links = {r['target_id'] for r in conn.execute(
            "SELECT target_id FROM links WHERE source_id = ?", (note_id,)
        ).fetchall()}
        my_links.update(r['source_id'] for r in conn.execute(
            "SELECT source_id FROM links WHERE target_id = ?", (note_id,)
        ).fetchall())

        # Score every other note
        all_notes = conn.execute("SELECT id, title FROM notes WHERE id != ?", (note_id,)).fetchall()
        scores = []
        for note in all_notes:
            nid = note['id']
            their_tags = {r['tag'] for r in conn.execute(
                "SELECT tag FROM tags WHERE note_id = ?", (nid,)
            ).fetchall()}
            their_links = {r['target_id'] for r in conn.execute(
                "SELECT target_id FROM links WHERE source_id = ?", (nid,)
            ).fetchall()}
            their_links.update(r['source_id'] for r in conn.execute(
                "SELECT source_id FROM links WHERE target_id = ?", (nid,)
            ).fetchall())

            # Jaccard-like similarity
            tag_overlap = len(my_tags & their_tags)
            tag_union = len(my_tags | their_tags) or 1
            link_overlap = len(my_links & their_links)
            link_union = len(my_links | their_links) or 1

            # Direct link bonus
            direct_link = 1.0 if nid in my_links else 0.0

            score = (tag_overlap / tag_union) * 0.4 + (link_overlap / link_union) * 0.3 + direct_link * 0.3
            if score > 0:
                scores.append({
                    "id": nid,
                    "title": note['title'],
                    "score": round(score, 3),
                    "shared_tags": sorted(my_tags & their_tags),
                    "direct_link": bool(direct_link),
                })

        scores.sort(key=lambda x: -x['score'])
        return scores


def get_tag_cooccurrence() -> dict:
    """Build tag co-occurrence matrix for semantic clustering."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t1.tag as tag_a, t2.tag as tag_b, COUNT(*) as count
            FROM tags t1 JOIN tags t2 ON t1.note_id = t2.note_id AND t1.tag < t2.tag
            GROUP BY t1.tag, t2.tag ORDER BY count DESC
        """).fetchall()

        matrix = []
        for r in rows:
            matrix.append({"source": r['tag_a'], "target": r['tag_b'], "weight": r['count']})
        return {"pairs": matrix}


def get_clusters() -> list[dict]:
    """Group notes into semantic clusters based on shared tags."""
    with get_db() as conn:
        # Get all tags and their notes
        tag_notes = {}
        for r in conn.execute("SELECT note_id, tag FROM tags"):
            tag_notes.setdefault(r['tag'], set()).add(r['note_id'])

        # Find clusters: notes that share 2+ tags
        note_cluster = {}
        cluster_id = 0
        all_notes = [r['id'] for r in conn.execute("SELECT id FROM notes").fetchall()]

        for note_id in all_notes:
            if note_id in note_cluster:
                continue
            # Find all notes similar to this one
            my_tags = {r['tag'] for r in conn.execute(
                "SELECT tag FROM tags WHERE note_id = ?", (note_id,)
            ).fetchall()}
            if not my_tags:
                continue

            cluster_members = {note_id}
            for other in all_notes:
                if other == note_id or other in note_cluster:
                    continue
                other_tags = {r['tag'] for r in conn.execute(
                    "SELECT tag FROM tags WHERE note_id = ?", (other,)
                ).fetchall()}
                shared = my_tags & other_tags
                if len(shared) >= 1:  # At least 1 shared tag
                    cluster_members.add(other)

            if len(cluster_members) > 1:
                for m in cluster_members:
                    note_cluster[m] = cluster_id
                cluster_id += 1

        # Build cluster objects
        clusters_map = {}
        for nid, cid in note_cluster.items():
            clusters_map.setdefault(cid, []).append(nid)

        result = []
        for cid, members in clusters_map.items():
            # Find shared tags for naming
            member_tags = []
            for m in members:
                tags = [r['tag'] for r in conn.execute(
                    "SELECT tag FROM tags WHERE note_id = ?", (m,)
                ).fetchall()]
                member_tags.append(set(tags))

            common_tags = member_tags[0]
            for ts in member_tags[1:]:
                common_tags = common_tags & ts

            notes_data = []
            for m in members:
                row = conn.execute("SELECT id, title FROM notes WHERE id = ?", (m,)).fetchone()
                if row:
                    notes_data.append({"id": row['id'], "title": row['title']})

            result.append({
                "id": cid,
                "label": ", ".join(sorted(common_tags)) if common_tags else f"Cluster {cid}",
                "common_tags": sorted(common_tags) if common_tags else [],
                "notes": notes_data,
                "size": len(members),
            })

        return result


def get_orphan_notes() -> list[dict]:
    """Find notes with no incoming or outgoing links."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT n.id, n.title, n.updated_at FROM notes n
            WHERE n.id NOT IN (SELECT source_id FROM links)
              AND n.id NOT IN (SELECT target_id FROM links)
        """).fetchall()
        return [dict(r) for r in rows]


def get_hub_notes(limit: int = 10) -> list[dict]:
    """Find the most connected notes (hubs)."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT n.id, n.title,
                (SELECT COUNT(*) FROM links WHERE source_id = n.id) as outgoing,
                (SELECT COUNT(*) FROM links WHERE target_id = n.id) as incoming,
                (SELECT COUNT(*) FROM links WHERE source_id = n.id) +
                (SELECT COUNT(*) FROM links WHERE target_id = n.id) as total
            FROM notes n ORDER BY total DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_note_stats(note_id: str) -> dict | None:
    """Get detailed statistics for a note."""
    with get_db() as conn:
        note = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not note:
            return None

        content = note['content']
        words = len(content.split()) if content else 0
        chars = len(content) if content else 0
        lines = content.count('\n') + 1 if content else 0
        read_time = max(1, words // 200)  # ~200 wpm

        outgoing = conn.execute(
            "SELECT COUNT(*) as c FROM links WHERE source_id = ?", (note_id,)
        ).fetchone()['c']
        incoming = conn.execute(
            "SELECT COUNT(*) as c FROM links WHERE target_id = ?", (note_id,)
        ).fetchone()['c']
        tags_count = conn.execute(
            "SELECT COUNT(*) as c FROM tags WHERE note_id = ?", (note_id,)
        ).fetchone()['c']

        return {
            "word_count": words,
            "char_count": chars,
            "line_count": lines,
            "read_time_min": read_time,
            "outgoing_links": outgoing,
            "incoming_links": incoming,
            "total_links": outgoing + incoming,
            "tags_count": tags_count,
        }
