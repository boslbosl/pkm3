"""LLM Wiki Markdown exporter (ARCHITECTURE §12).

Emits one Markdown file per session with YAML frontmatter, capsule sections
(best-effort, no LLM in MVP), and a link back to the immutable raw artifact,
plus an export manifest. Re-export is idempotent via export_hash.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..dedupe import export_hash
from ..service import Vault, normalize_status

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str | None, fallback: str) -> str:
    base = (text or "").strip().lower()
    base = _SLUG_RE.sub("-", base).strip("-")
    return base[:60] or fallback


def _date_part(started_at: str | None, imported_at: str) -> str:
    raw = started_at or imported_at or ""
    return raw[:10] if len(raw) >= 10 else "undated"


def _yaml_value(v) -> str:
    if v is None:
        return "null"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{}\"']", s):
        return json.dumps(s)
    return s


def render_markdown(session, messages, snippets, tags, raw_artifact_path: str) -> tuple[str, str]:
    """Return (full_markdown_with_frontmatter, body_only) — body drives export_hash."""
    project = session["project_name"] or "unsorted"
    commands = [s["value"] for s in snippets if s["kind"] == "command"]
    files = [s["value"] for s in snippets if s["kind"] == "file_path"]

    first_user = next(
        (m["content"] for m in messages if m["role"] == "user" and (m["content"] or "").strip()),
        "",
    )

    lines: list[str] = []
    lines.append(f"# {session['title'] or 'Untitled session'}")
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append(first_user.strip()[:1000] if first_user else "_Not captured._")
    lines.append("")
    lines.append("## Key outcome")
    lines.append("")
    lines.append(session["summary"] or "_To be summarized._")
    lines.append("")
    lines.append("## Important decisions")
    lines.append("")
    lines.append("_To be summarized._")
    lines.append("")
    lines.append("## Files and commands")
    lines.append("")
    if files:
        lines.append("**Files:**")
        lines.extend(f"- `{p}`" for p in files)
        lines.append("")
    if commands:
        lines.append("**Commands:**")
        lines.extend(f"- `{c}`" for c in commands)
        lines.append("")
    if not files and not commands:
        lines.append("_None extracted._")
        lines.append("")
    lines.append("## Conversation excerpts")
    lines.append("")
    for m in messages:
        content = (m["content"] or "").strip()
        if not content:
            continue
        lines.append(f"### {m['role']}")
        lines.append("")
        lines.append(content)
        lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("_To be reviewed._")
    lines.append("")
    lines.append("## Raw evidence")
    lines.append("")
    lines.append(f"- Source artifact: `{raw_artifact_path}`")
    lines.append("")

    body = "\n".join(lines)

    fm: dict[str, object] = {
        "source_tool": session["source_tool"],
        "source_kind": session["source_kind"],
        "project": project,
        "session_id": session["id"],
        "source_session_id": session["source_session_id"],
        "title": session["title"],
        "started_at": session["started_at"],
        "status": session["status"],
        "raw_artifact": raw_artifact_path,
        "dedupe_key": session["dedupe_key"],
        "sensitivity": session["sensitivity"],
        "tags": tags,
    }
    fm_lines = ["---"]
    for k, v in fm.items():
        if k == "tags":
            fm_lines.append("tags: [" + ", ".join(_yaml_value(t) for t in v) + "]")
        else:
            fm_lines.append(f"{k}: {_yaml_value(v)}")
    fm_lines.append("---")
    full = "\n".join(fm_lines) + "\n\n" + body + "\n"
    return full, body


@dataclass
class ExportSummary:
    exported: list[str] = field(default_factory=list)
    skipped: int = 0
    out_path: Path | None = None


def export_llmwiki(
    vault: Vault,
    out_dir: Path,
    status: str = "wiki_ready",
    mark_exported: bool = False,
) -> ExportSummary:
    canonical_status = normalize_status(status)
    out_dir = out_dir.expanduser().resolve()
    sessions_dir = out_dir / "raw" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    conn = vault.conn
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO export_runs(target, out_path, status_filter, started_at) VALUES (?,?,?,?)",
        ("llmwiki", str(out_dir), canonical_status, started),
    )
    run_id = cur.lastrowid

    rows = vault.list_sessions(status=canonical_status, limit=100000)
    summary = ExportSummary(out_path=out_dir)
    manifest_items = []

    for session in rows:
        sid = session["id"]
        messages = vault.get_messages(sid)
        snippets = vault.get_snippets(sid)
        tags = vault.get_tags(sid)
        artifact = conn.execute(
            "SELECT stored_path FROM raw_artifacts WHERE id = ?",
            (session["raw_artifact_id"],),
        ).fetchone()
        raw_path = artifact["stored_path"] if artifact else ""

        full_md, body = render_markdown(session, messages, snippets, tags, raw_path)
        ehash = export_hash(body.strip("\n"))

        project_slug = _slug(session["project_name"], "unsorted")
        fname = (
            f"{_date_part(session['started_at'], session['imported_at'])}"
            f"_{session['source_tool']}_{_slug(session['title'], sid[:8])}.md"
        )
        target = sessions_dir / project_slug / fname
        target.parent.mkdir(parents=True, exist_ok=True)

        # idempotency: skip if an identical export already exists on disk
        if target.exists() and export_hash(_body_of(target.read_text(encoding="utf-8"))) == ehash:
            summary.skipped += 1
        else:
            target.write_text(full_md, encoding="utf-8")
            summary.exported.append(sid)

        conn.execute(
            "INSERT INTO export_items(export_run_id, session_id, out_file, export_hash)"
            " VALUES (?,?,?,?)",
            (run_id, sid, str(target.relative_to(out_dir)), ehash),
        )
        manifest_items.append(
            {
                "session_id": sid,
                "title": session["title"],
                "project": session["project_name"],
                "source_tool": session["source_tool"],
                "out_file": str(target.relative_to(out_dir)),
                "export_hash": ehash,
                "raw_artifact": raw_path,
            }
        )
        if mark_exported:
            conn.execute(
                "UPDATE sessions SET status = 'exported' WHERE id = ?", (sid,)
            )

    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE export_runs SET finished_at=?, exported_count=?, skipped_count=? WHERE id=?",
        (finished, len(summary.exported), summary.skipped, run_id),
    )

    manifest = {
        "target": "llmwiki",
        "generated_at": finished,
        "status_filter": canonical_status,
        "count": len(manifest_items),
        "items": manifest_items,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    conn.commit()
    return summary


def _body_of(markdown: str) -> str:
    """Strip leading YAML frontmatter so export_hash compares body only."""
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n").rstrip("\n")
    return markdown.rstrip("\n")
