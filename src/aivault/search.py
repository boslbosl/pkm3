"""FTS5 indexing and query helpers (ARCHITECTURE §5, PRD §6.3)."""

from __future__ import annotations

import sqlite3

from .models import CanonicalSession


def index_session(
    conn: sqlite3.Connection,
    session_id: str,
    session: CanonicalSession,
    notes: str = "",
) -> None:
    """(Re)build the FTS row for a session. Idempotent: delete-then-insert."""
    prompts = "\n".join(m.content for m in session.messages if m.role == "user")
    responses = "\n".join(
        m.content for m in session.messages if m.role in ("assistant", "model")
    )
    conn.execute("DELETE FROM fts_sessions WHERE session_id = ?", (session_id,))
    conn.execute(
        "INSERT INTO fts_sessions"
        "(session_id, title, prompts, responses, commands, file_paths, summary, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id,
            session.title or "",
            prompts,
            responses,
            "\n".join(session.commands),
            "\n".join(session.file_paths),
            session.summary or "",
            notes or "",
        ),
    )


def update_notes(conn: sqlite3.Connection, session_id: str, notes: str) -> None:
    conn.execute(
        "UPDATE fts_sessions SET notes = ? WHERE session_id = ?", (notes, session_id)
    )


def search(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[str]:
    """Return session_ids ranked by FTS relevance."""
    rows = conn.execute(
        "SELECT session_id FROM fts_sessions WHERE fts_sessions MATCH ? "
        "ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    return [r["session_id"] for r in rows]
