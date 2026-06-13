"""Codex JSONL adapter (ARCHITECTURE §7.2).

Codex CLI rollout logs are JSONL. Shapes seen across versions:

  {"type":"session_meta","payload":{"id":"...","timestamp":"...","cwd":"..."}}
  {"type":"response_item","payload":{"type":"message","role":"user",
     "content":[{"type":"input_text","text":"..."}]}}
  {"role":"assistant","content":[{"type":"output_text","text":"..."}]}   # flat

Parsed defensively (§18.1). A file is treated as one session; session id/cwd
come from session_meta when present.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import CanonicalMessage, CanonicalSession, SourceCandidate
from .base import (
    SourceAdapter,
    dedupe_keep_order,
    extract_commands_and_paths,
    extract_text,
)

_DISCOVER_GLOBS = [
    (Path.home() / ".codex" / "sessions", "**/*.jsonl", "native"),
    (Path("/mnt/c/Users"), "*/.codex/sessions/**/*.jsonl", "wsl"),
]


class CodexAdapter(SourceAdapter):
    source_type = "codex"
    source_kind = "local-log"

    def discover(self) -> list[SourceCandidate]:
        out: list[SourceCandidate] = []
        for root, pattern, os_ctx in _DISCOVER_GLOBS:
            if not root.exists():
                continue
            files = list(root.glob(pattern))
            if files:
                out.append(
                    SourceCandidate(
                        source_tool=self.source_type,
                        source_kind=self.source_kind,
                        path=root,
                        os_context=os_ctx,
                        estimated_sessions=len(files),
                    )
                )
        return out

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        sid: str | None = None
        cwd: str | None = None
        meta_ts: str | None = None
        messages: list[CanonicalMessage] = []
        commands: list[str] = []
        paths: list[str] = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(obj, dict):
                continue

            # session_meta carries id/cwd/timestamp
            if obj.get("type") == "session_meta":
                payload = obj.get("payload") or {}
                sid = sid or payload.get("id") or payload.get("session_id")
                cwd = cwd or payload.get("cwd")
                meta_ts = meta_ts or payload.get("timestamp")
                continue

            # message may be flat or wrapped in payload / response_item
            msg = obj
            if obj.get("type") in ("response_item", "event") and isinstance(
                obj.get("payload"), dict
            ):
                msg = obj["payload"]

            role = msg.get("role")
            content = msg.get("content")
            if role is None and msg.get("type") == "message":
                role = msg.get("role")
            if role is None:
                continue  # skip non-message items (tool calls etc.)

            body = extract_text(content)
            if not body:
                continue
            cmds, ps = extract_commands_and_paths(content)
            commands.extend(cmds)
            paths.extend(ps)
            messages.append(
                CanonicalMessage(role=role, content=body, created_at=msg.get("timestamp"))
            )

        if not messages:
            return []

        times = [m.created_at for m in messages if m.created_at]
        started = meta_ts or (times[0] if times else None)
        ended = times[-1] if times else meta_ts
        project = Path(cwd).name if cwd else None
        title = _title_from_first(messages)
        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                source_session_id=sid,
                title=title,
                started_at=started,
                ended_at=ended,
                project_name=project,
                messages=messages,
                commands=dedupe_keep_order(commands),
                file_paths=dedupe_keep_order(paths),
            )
        ]


def _title_from_first(msgs: list[CanonicalMessage]) -> str | None:
    for m in msgs:
        if m.role == "user" and m.content.strip():
            return m.content.strip().splitlines()[0][:80]
    return None
