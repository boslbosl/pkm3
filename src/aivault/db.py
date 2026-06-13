"""SQLite storage + FTS5 schema (ARCHITECTURE §5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_tool TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    root_path   TEXT,
    os_context  TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE(source_tool, source_kind, root_path)
);

CREATE TABLE IF NOT EXISTS import_batches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_tool    TEXT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    imported_count INTEGER DEFAULT 0,
    skipped_count  INTEGER DEFAULT 0,
    note           TEXT
);

CREATE TABLE IF NOT EXISTS raw_artifacts (
    id              TEXT PRIMARY KEY,
    source_tool     TEXT NOT NULL,
    source_kind     TEXT NOT NULL,
    original_path   TEXT,
    stored_path     TEXT NOT NULL,
    artifact_hash   TEXT NOT NULL UNIQUE,
    bytes           INTEGER,
    os_context      TEXT DEFAULT 'native',
    imported_at     TEXT NOT NULL,
    import_batch_id INTEGER REFERENCES import_batches(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    root_path  TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                 TEXT PRIMARY KEY,
    source_tool        TEXT NOT NULL,
    source_kind        TEXT NOT NULL,
    source_session_id  TEXT,
    project_id         INTEGER REFERENCES projects(id),
    title              TEXT,
    started_at         TEXT,
    ended_at           TEXT,
    imported_at        TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'new',
    os_context         TEXT DEFAULT 'native',
    raw_artifact_id    TEXT REFERENCES raw_artifacts(id),
    source_fingerprint TEXT UNIQUE,
    content_hash       TEXT,
    dedupe_key         TEXT,
    sensitivity        TEXT DEFAULT 'unknown',
    summary            TEXT,
    notes              TEXT,
    message_count      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq        INTEGER NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT,
    created_at TEXT,
    meta       TEXT
);

CREATE TABLE IF NOT EXISTS snippets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,   -- command | file_path | code
    value      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS session_tags (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (session_id, tag_id)
);

CREATE TABLE IF NOT EXISTS export_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    target         TEXT NOT NULL,
    out_path       TEXT NOT NULL,
    status_filter  TEXT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    exported_count INTEGER DEFAULT 0,
    skipped_count  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS export_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    export_run_id INTEGER REFERENCES export_runs(id),
    session_id    TEXT REFERENCES sessions(id),
    out_file      TEXT,
    export_hash   TEXT
);

CREATE TABLE IF NOT EXISTS redaction_findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    confidence  TEXT NOT NULL,   -- low | medium | high
    excerpt     TEXT,
    message_seq INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sessions_status  ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_source  ON sessions(source_tool);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_snippets_session ON snippets(session_id);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_sessions USING fts5(
    session_id UNINDEXED,
    title, prompts, responses, commands, file_paths, summary, notes,
    tokenize = 'porter unicode61'
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
