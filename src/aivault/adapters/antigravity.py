"""Antigravity (IDE + CLI) adapter (ARCHITECTURE §7.4).

Antigravity's on-disk format is not contractually stable, so this adapter is
deliberately shape-agnostic (§18.1): it walks JSONL lines and accepts a message
whether ``role``/``content`` sit at the top level, under ``message``, or under
``payload``. Session id and working dir are pulled from whatever common keys are
present. Files with no recognizable messages yield nothing (the generic folder
importer remains the fallback for those).
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

_SID_KEYS = ("sessionId", "session_id", "conversationId", "conversation_id", "id")
_CWD_KEYS = ("cwd", "workspace", "workspaceRoot", "project", "projectRoot", "rootPath")


class AntigravityAdapter(SourceAdapter):
    source_type = "antigravity"
    source_kind = "local-log"
    home_subpaths = (
        ".antigravity",
        ".antigravity/sessions",
        ".config/Antigravity",
        "AppData/Roaming/Antigravity",
        "AppData/Local/Antigravity",
        "Library/Application Support/Antigravity",
    )
    file_glob = "**/*.jsonl"

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

            sid = sid or _first(obj, _SID_KEYS)
            cwd = cwd or _first(obj, _CWD_KEYS)

            # unwrap common envelopes
            inner = obj
            if isinstance(obj.get("message"), dict):
                inner = obj["message"]
            elif isinstance(obj.get("payload"), dict):
                inner = obj["payload"]
                sid = sid or _first(inner, _SID_KEYS)
                cwd = cwd or _first(inner, _CWD_KEYS)

            role = inner.get("role")
            content = inner.get("content")
            if role is None or content is None:
                continue
            body = extract_text(content)
            if not body:
                continue
            cmds, ps = extract_commands_and_paths(content)
            commands.extend(cmds)
            paths.extend(ps)
            ts = inner.get("timestamp") or obj.get("timestamp")
            meta_ts = meta_ts or ts
            messages.append(CanonicalMessage(role=str(role), content=body, created_at=ts))

        if not messages:
            return []

        times = [m.created_at for m in messages if m.created_at]
        project = Path(cwd).name if cwd else None
        title = next(
            (m.content.strip().splitlines()[0][:80] for m in messages if m.role == "user" and m.content.strip()),
            None,
        )
        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                source_session_id=sid,
                title=title,
                started_at=(times[0] if times else meta_ts),
                ended_at=(times[-1] if times else meta_ts),
                project_name=project,
                project_root=cwd,
                messages=messages,
                commands=dedupe_keep_order(commands),
                file_paths=dedupe_keep_order(paths),
            )
        ]


def _first(obj: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None
