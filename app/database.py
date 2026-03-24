import sqlite3
from contextlib import contextmanager
from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    filepath    TEXT NOT NULL UNIQUE,
    content     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS links (
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    context     TEXT,
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE IF NOT EXISTS tags (
    note_id     TEXT NOT NULL,
    tag         TEXT NOT NULL,
    PRIMARY KEY (note_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id);

-- Semantic collections: group notes into named clusters
CREATE TABLE IF NOT EXISTS collections (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    color       TEXT DEFAULT '#89b4fa',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collection_notes (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    note_id       TEXT NOT NULL,
    PRIMARY KEY (collection_id, note_id)
);

-- Link types for semantic relationships
CREATE TABLE IF NOT EXISTS link_types (
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    rel_type    TEXT NOT NULL DEFAULT 'references',
    PRIMARY KEY (source_id, target_id)
);

-- Note metadata: pinned, archived, word count, etc.
CREATE TABLE IF NOT EXISTS note_meta (
    note_id     TEXT PRIMARY KEY,
    pinned      INTEGER DEFAULT 0,
    archived    INTEGER DEFAULT 0,
    word_count  INTEGER DEFAULT 0,
    read_time   INTEGER DEFAULT 0
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    id,
    title,
    content,
    content=notes,
    content_rowid=rowid
);
"""

FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, id, title, content) VALUES (new.rowid, new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, id, title, content) VALUES('delete', old.rowid, old.id, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, id, title, content) VALUES('delete', old.rowid, old.id, old.title, old.content);
    INSERT INTO notes_fts(rowid, id, title, content) VALUES (new.rowid, new.id, new.title, new.content);
END;
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(FTS_SCHEMA)
        conn.executescript(FTS_TRIGGERS)
