"""Claude Code JSONL adapter (ARCHITECTURE §7.1).

Real Claude Code logs are JSONL where each line is an event. Shapes vary by
version; we parse defensively (§18.1). Recognized line types:

  {"type":"summary","summary":"...","leafUuid":"..."}
  {"type":"user","sessionId":"...","cwd":"...","timestamp":"...",
   "message":{"role":"user","content": <str|list>}}
  {"type":"assistant", ..., "message":{"role":"assistant","content": <list>}}

Multiple sessionIds in one file produce multiple CanonicalSessions.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import CanonicalMessage, CanonicalSession
from .base import (
    SourceAdapter,
    dedupe_keep_order,
    extract_commands_and_paths,
    extract_text,
)


class ClaudeCodeAdapter(SourceAdapter):
    source_type = "claude-code"
    source_kind = "local-log"
    # discovered across OS contexts via the home-based default discover()
    home_subpaths = (".claude/projects", ".config/claude/projects")
    file_glob = "**/*.jsonl"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        # session_id -> working dict
        groups: dict[str, dict] = {}
        # leafUuid -> summary text (summary lines reference the session's last msg)
        summaries: dict[str, str] = {}
        order: list[str] = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # tolerate malformed lines
            if not isinstance(obj, dict):
                continue

            ltype = obj.get("type")
            if ltype == "summary":
                if isinstance(obj.get("summary"), str):
                    summaries[obj.get("leafUuid") or ""] = obj["summary"]
                continue
            if ltype not in ("user", "assistant"):
                continue

            sid = obj.get("sessionId") or obj.get("session_id") or "unknown"
            if sid not in groups:
                groups[sid] = {
                    "cwd": obj.get("cwd"),
                    "messages": [],
                    "commands": [],
                    "paths": [],
                    "uuids": set(),
                }
                order.append(sid)
            g = groups[sid]
            if g["cwd"] is None and obj.get("cwd"):
                g["cwd"] = obj["cwd"]
            if obj.get("uuid"):
                g["uuids"].add(obj["uuid"])

            message = obj.get("message") or {}
            role = message.get("role") or ltype
            content = message.get("content")
            body = extract_text(content)
            cmds, paths = extract_commands_and_paths(content)
            g["commands"].extend(cmds)
            g["paths"].extend(paths)
            ts = obj.get("timestamp")
            g["messages"].append(
                CanonicalMessage(role=role, content=body, created_at=ts)
            )

        sessions: list[CanonicalSession] = []
        for sid in order:
            g = groups[sid]
            msgs: list[CanonicalMessage] = g["messages"]
            if not msgs:
                continue
            times = [m.created_at for m in msgs if m.created_at]
            project = Path(g["cwd"]).name if g["cwd"] else None
            # map a summary to this session only if it references one of its messages
            title = next(
                (summaries[u] for u in g["uuids"] if u in summaries),
                _title_from_first(msgs),
            )
            sessions_project_root = g["cwd"]
            sessions.append(
                CanonicalSession(
                    source_tool=self.source_type,
                    source_kind=self.source_kind,
                    source_session_id=None if sid == "unknown" else sid,
                    title=title,
                    started_at=times[0] if times else None,
                    ended_at=times[-1] if times else None,
                    project_name=project,
                    project_root=sessions_project_root,
                    messages=msgs,
                    commands=dedupe_keep_order(g["commands"]),
                    file_paths=dedupe_keep_order(g["paths"]),
                )
            )
        return sessions


def _title_from_first(msgs: list[CanonicalMessage]) -> str | None:
    for m in msgs:
        if m.role == "user" and m.content.strip():
            first = m.content.strip().splitlines()[0]
            return first[:80]
    return None
