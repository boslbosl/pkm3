"""Pure API layer for the web frontend (ARCHITECTURE §12a, §19.3).

Functions take a ``Vault`` and return plain JSON-serializable dicts. No HTTP,
no sockets — directly unit-testable. The server module is a thin transport.
"""

from __future__ import annotations

from ..service import Vault, normalize_status

# columns surfaced as full session metadata (PRD §6.7)
_SESSION_FIELDS = (
    "id",
    "source_tool",
    "source_kind",
    "source_session_id",
    "title",
    "project_name",
    "project_root",
    "os_context",
    "status",
    "sensitivity",
    "started_at",
    "ended_at",
    "imported_at",
    "message_count",
    "summary",
    "notes",
    "content_hash",
    "dedupe_key",
    "source_fingerprint",
    "raw_artifact_id",
)


def _row_to_dict(row) -> dict:
    keys = row.keys()
    return {f: (row[f] if f in keys else None) for f in _SESSION_FIELDS}


def stats(vault: Vault) -> dict:
    conn = vault.conn
    base = vault.counts()

    def breakdown(col: str) -> dict:
        rows = conn.execute(
            f"SELECT {col} AS k, COUNT(*) AS n FROM sessions GROUP BY {col} ORDER BY n DESC"
        ).fetchall()
        return {(r["k"] or "unknown"): r["n"] for r in rows}

    base["by_source"] = breakdown("source_tool")
    base["by_status"] = breakdown("status")
    base["by_os"] = breakdown("os_context")
    return base


def projects(vault: Vault) -> list[dict]:
    rows = vault.conn.execute(
        "SELECT p.name, p.root_path, COUNT(s.id) AS n "
        "FROM projects p LEFT JOIN sessions s ON s.project_id = p.id "
        "GROUP BY p.id ORDER BY n DESC, p.name"
    ).fetchall()
    return [
        {"name": r["name"], "root_path": r["root_path"], "sessions": r["n"]}
        for r in rows
    ]


def _matches(row, source, project, status, os_context) -> bool:
    if source and row["source_tool"] != source:
        return False
    if project and row["project_name"] != project:
        return False
    if status and row["status"] != normalize_status(status):
        return False
    if os_context and row["os_context"] != os_context:
        return False
    return True


def list_sessions(
    vault: Vault,
    group: str = "project",
    q: str | None = None,
    source: str | None = None,
    project: str | None = None,
    status: str | None = None,
    os_context: str | None = None,
    limit: int = 500,
) -> dict:
    """Return sessions grouped by project / source / time."""
    if q:
        rows = [r for r in vault.search(q, limit=limit)
                if _matches(r, source, project, status, os_context)]
    else:
        rows = vault.list_sessions(
            source=source, project=project, status=status,
            os_context=os_context, limit=limit,
        )

    sessions = [_row_to_dict(r) for r in rows]

    groups: dict[str, dict] = {}
    order: list[str] = []

    def bucket(key: str, label: str):
        if key not in groups:
            groups[key] = {"key": key, "label": label, "sessions": []}
            order.append(key)
        return groups[key]

    if group == "time":
        bucket("timeline", "Timeline (newest first)")
        for s in sessions:
            groups["timeline"]["sessions"].append(s)
    elif group == "source":
        for s in sessions:
            key = s["source_tool"] or "unknown"
            label = key if not s["os_context"] or s["os_context"] == "native" else f"{key} ({s['os_context']})"
            bucket(f"{key}|{s['os_context']}", label)["sessions"].append(s)
    else:  # project / repo
        for s in sessions:
            key = s["project_root"] or s["project_name"] or "(unsorted)"
            label = s["project_name"] or s["project_root"] or "(unsorted)"
            bucket(key, label)["sessions"].append(s)

    return {
        "group_by": group,
        "count": len(sessions),
        "groups": [groups[k] for k in order],
    }


def session_detail(vault: Vault, session_id: str) -> dict | None:
    s = vault.get_session(session_id)
    if not s:
        return None
    sid = s["id"]
    artifact = vault.conn.execute(
        "SELECT stored_path, original_path, artifact_hash, bytes FROM raw_artifacts WHERE id = ?",
        (s["raw_artifact_id"],),
    ).fetchone()
    data = _row_to_dict(s)
    data["tags"] = vault.get_tags(sid)
    data["commands"] = [r["value"] for r in vault.get_snippets(sid, "command")]
    data["files"] = [r["value"] for r in vault.get_snippets(sid, "file_path")]
    data["redaction_findings"] = [
        {"kind": f["kind"], "confidence": f["confidence"], "excerpt": f["excerpt"]}
        for f in vault.get_findings(sid)
    ]
    data["raw_artifact"] = (
        {
            "stored_path": artifact["stored_path"],
            "original_path": artifact["original_path"],
            "artifact_hash": artifact["artifact_hash"],
            "bytes": artifact["bytes"],
        }
        if artifact
        else None
    )
    data["messages"] = [
        {"seq": m["seq"], "role": m["role"], "content": m["content"], "created_at": m["created_at"]}
        for m in vault.get_messages(sid)
    ]
    return data
