"""Application services: the high-level operations the CLI calls.

Owns the import engine, triage, search, and export orchestration. Adapters
return CanonicalSession objects; this module performs all DB writes and dedupe
(ARCHITECTURE §6, §9).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import db, search
from .adapters.base import get_adapter
from .config import VaultConfig, create_vault_dirs
from .dedupe import content_hash, source_fingerprint
from .models import STATUSES, CanonicalSession
from .platform_paths import infer_os_context
from .raw_store import store_artifact
from .redaction import scan_session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_status(status: str) -> str:
    """Accept hyphenated CLI form (`wiki-ready`) -> canonical (`wiki_ready`)."""
    s = status.strip().lower().replace("-", "_")
    if s not in STATUSES:
        raise ValueError(f"Invalid status '{status}'. Allowed: {', '.join(STATUSES)}")
    return s


# ---------------------------------------------------------------------------
# Vault lifecycle
# ---------------------------------------------------------------------------

def init_vault(root: Path) -> VaultConfig:
    create_vault_dirs(root)
    cfg = VaultConfig(root=root)
    cfg.save()
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    conn.close()
    return cfg


def open_vault(root: Path) -> tuple[VaultConfig, "Vault"]:
    cfg = VaultConfig.load(root)
    return cfg, Vault(cfg)


@dataclass
class ImportResult:
    imported: list[str] = field(default_factory=list)   # session ids
    skipped: int = 0
    findings: int = 0


class Vault:
    def __init__(self, cfg: VaultConfig):
        self.cfg = cfg
        self.conn = db.connect(cfg.db_path)

    def close(self) -> None:
        self.conn.close()

    # --- helpers ---------------------------------------------------------
    def _get_or_create_project(self, name: str | None, root_path: str | None) -> int | None:
        if not name:
            return None
        row = self.conn.execute(
            "SELECT id, root_path FROM projects WHERE name = ?", (name,)
        ).fetchone()
        if row:
            # backfill repo root path the first time we learn it
            if root_path and not row["root_path"]:
                self.conn.execute(
                    "UPDATE projects SET root_path = ? WHERE id = ?", (root_path, row["id"])
                )
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO projects(name, root_path, created_at) VALUES(?, ?, ?)",
            (name, root_path, _now()),
        )
        return cur.lastrowid

    # --- import engine ---------------------------------------------------
    def import_file(
        self, path: Path, source_tool: str, os_context: str | None = None
    ) -> ImportResult:
        try:
            raw_bytes = path.read_bytes()
        except (PermissionError, OSError):
            # tolerate unreadable files during cross-OS scans (ARCHITECTURE §8a)
            return ImportResult(skipped=1)
        ctx = os_context or infer_os_context(str(path))
        return self._import_bytes(raw_bytes, str(path), source_tool, ctx)

    def _import_bytes(
        self, raw_bytes: bytes, original_path: str, source_tool: str, os_context: str = "native"
    ) -> ImportResult:
        result = ImportResult()
        adapter = get_adapter(source_tool)

        stored = store_artifact(self.cfg, source_tool, original_path, raw_bytes)

        # artifact-hash dedupe: identical bytes already imported -> skip whole file
        existing = self.conn.execute(
            "SELECT id FROM raw_artifacts WHERE artifact_hash = ?",
            (stored.artifact_hash,),
        ).fetchone()
        if existing:
            result.skipped += 1
            return result

        artifact_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO raw_artifacts"
            "(id, source_tool, source_kind, original_path, stored_path, artifact_hash, bytes, os_context, imported_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                source_tool,
                adapter.source_kind,
                original_path,
                stored.stored_rel_path,
                stored.artifact_hash,
                stored.bytes,
                os_context,
                _now(),
            ),
        )

        sessions = adapter.normalize(raw_bytes, original_path)
        for cs in sessions:
            sid = self._persist_session(cs, artifact_id, original_path, os_context)
            if sid is None:
                result.skipped += 1
            else:
                result.imported.append(sid)
                result.findings += self._persist_findings(sid, cs)

        self.conn.commit()
        return result

    def _persist_session(
        self, cs: CanonicalSession, artifact_id: str, original_path: str, os_context: str = "native"
    ) -> str | None:
        fp = source_fingerprint(cs.source_tool, original_path, cs.source_session_id)
        ch = content_hash(cs)

        existing = self.conn.execute(
            "SELECT id FROM sessions WHERE source_fingerprint = ?", (fp,)
        ).fetchone()
        if existing:
            # same logical session already present: refresh light metadata, keep raw
            self.conn.execute(
                "UPDATE sessions SET content_hash = ?, summary = COALESCE(summary, ?) WHERE id = ?",
                (ch, cs.summary, existing["id"]),
            )
            return None  # not a new import

        session_id = str(uuid.uuid4())
        project_id = self._get_or_create_project(cs.project_name, cs.project_root)
        self.conn.execute(
            "INSERT INTO sessions"
            "(id, source_tool, source_kind, source_session_id, project_id, title,"
            " started_at, ended_at, imported_at, status, os_context, raw_artifact_id,"
            " source_fingerprint, content_hash, dedupe_key, sensitivity, summary, message_count)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                cs.source_tool,
                cs.source_kind,
                cs.source_session_id,
                project_id,
                cs.title,
                cs.started_at,
                cs.ended_at,
                _now(),
                "new",
                os_context,
                artifact_id,
                fp,
                ch,
                f"sha256:{ch}",
                cs.sensitivity or self.cfg.default_sensitivity,
                cs.summary,
                len(cs.messages),
            ),
        )
        for seq, m in enumerate(cs.messages):
            self.conn.execute(
                "INSERT INTO messages(session_id, seq, role, content, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, seq, m.role, m.content, m.created_at),
            )
        for cmd in cs.commands:
            self.conn.execute(
                "INSERT INTO snippets(session_id, kind, value) VALUES (?, 'command', ?)",
                (session_id, cmd),
            )
        for fpath in cs.file_paths:
            self.conn.execute(
                "INSERT INTO snippets(session_id, kind, value) VALUES (?, 'file_path', ?)",
                (session_id, fpath),
            )
        search.index_session(self.conn, session_id, cs)
        return session_id

    def _persist_findings(self, session_id: str, cs: CanonicalSession) -> int:
        findings = scan_session(cs)
        for f in findings:
            self.conn.execute(
                "INSERT INTO redaction_findings(session_id, kind, confidence, excerpt, message_seq)"
                " VALUES (?, ?, ?, ?, ?)",
                (session_id, f.kind, f.confidence, f.excerpt, f.message_seq),
            )
        return len(findings)

    # --- discovery / sync ------------------------------------------------
    def discover(self, os_scope: str = "native") -> list:
        from .adapters.base import _build_registry

        candidates = []
        for adapter in _build_registry().values():
            candidates.extend(adapter.discover(os_scope))
        return candidates

    def sync(self, source_tool: str, os_scope: str = "native") -> ImportResult:
        adapter = get_adapter(source_tool)
        total = ImportResult()
        for candidate in adapter.discover(os_scope):
            try:
                files = sorted(candidate.path.glob(adapter.file_glob))
            except (PermissionError, OSError):
                continue
            for jsonl in files:
                res = self.import_file(jsonl, source_tool, os_context=candidate.os_context)
                total.imported.extend(res.imported)
                total.skipped += res.skipped
                total.findings += res.findings
        return total

    # --- triage ----------------------------------------------------------
    def mark(self, session_id: str, status: str) -> bool:
        canonical = normalize_status(status)
        cur = self.conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?", (canonical, session_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def add_tags(self, session_id: str, tags: list[str]) -> bool:
        row = self.conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return False
        for name in tags:
            name = name.strip()
            if not name:
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,)
            )
            tag_id = self.conn.execute(
                "SELECT id FROM tags WHERE name = ?", (name,)
            ).fetchone()["id"]
            self.conn.execute(
                "INSERT OR IGNORE INTO session_tags(session_id, tag_id) VALUES (?, ?)",
                (session_id, tag_id),
            )
        self.conn.commit()
        return True

    def set_notes(self, session_id: str, notes: str) -> bool:
        cur = self.conn.execute(
            "UPDATE sessions SET notes = ? WHERE id = ?", (notes, session_id)
        )
        if cur.rowcount:
            search.update_notes(self.conn, session_id, notes)
            self.conn.commit()
            return True
        return False

    # --- queries ---------------------------------------------------------
    def list_sessions(
        self,
        source: str | None = None,
        project: str | None = None,
        status: str | None = None,
        os_context: str | None = None,
        limit: int = 100,
    ) -> list:
        sql = (
            "SELECT s.*, p.name AS project_name, p.root_path AS project_root "
            "FROM sessions s LEFT JOIN projects p ON p.id = s.project_id WHERE 1=1"
        )
        params: list = []
        if source:
            sql += " AND s.source_tool = ?"
            params.append(source)
        if project:
            sql += " AND p.name = ?"
            params.append(project)
        if status:
            sql += " AND s.status = ?"
            params.append(normalize_status(status))
        if os_context:
            sql += " AND s.os_context = ?"
            params.append(os_context)
        sql += " ORDER BY COALESCE(s.started_at, s.imported_at) DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def search(self, query: str, limit: int = 50) -> list:
        ids = search.search(self.conn, query, limit)
        if not ids:
            return []
        rows = []
        for sid in ids:  # preserve rank order
            r = self.conn.execute(
                "SELECT s.*, p.name AS project_name, p.root_path AS project_root "
                "FROM sessions s LEFT JOIN projects p ON p.id = s.project_id WHERE s.id = ?",
                (sid,),
            ).fetchone()
            if r:
                rows.append(r)
        return rows

    def get_session(self, session_id: str):
        # allow short-id prefix match for convenience
        row = self.conn.execute(
            "SELECT s.*, p.name AS project_name, p.root_path AS project_root "
            "FROM sessions s LEFT JOIN projects p ON p.id = s.project_id "
            "WHERE s.id = ? OR s.id LIKE ?",
            (session_id, session_id + "%"),
        ).fetchone()
        return row

    def get_messages(self, session_id: str) -> list:
        return self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY seq", (session_id,)
        ).fetchall()

    def get_snippets(self, session_id: str, kind: str | None = None) -> list:
        if kind:
            return self.conn.execute(
                "SELECT * FROM snippets WHERE session_id = ? AND kind = ?",
                (session_id, kind),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM snippets WHERE session_id = ?", (session_id,)
        ).fetchall()

    def get_tags(self, session_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT t.name FROM tags t JOIN session_tags st ON st.tag_id = t.id "
            "WHERE st.session_id = ? ORDER BY t.name",
            (session_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def get_findings(self, session_id: str) -> list:
        return self.conn.execute(
            "SELECT * FROM redaction_findings WHERE session_id = ?", (session_id,)
        ).fetchall()

    def counts(self) -> dict:
        def one(q: str) -> int:
            return self.conn.execute(q).fetchone()[0]

        return {
            "sessions": one("SELECT COUNT(*) FROM sessions"),
            "messages": one("SELECT COUNT(*) FROM messages"),
            "raw_artifacts": one("SELECT COUNT(*) FROM raw_artifacts"),
            "projects": one("SELECT COUNT(*) FROM projects"),
            "wiki_ready": one("SELECT COUNT(*) FROM sessions WHERE status='wiki_ready'"),
            "findings": one("SELECT COUNT(*) FROM redaction_findings"),
        }
