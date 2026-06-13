"""Cline adapter (PRD §7, near-term).

Cline (VS Code extension) stores each task under the editor's globalStorage as
``api_conversation_history.json`` — an array of messages whose ``content`` is a
list of typed blocks (Anthropic-style). Version-tolerant (ARCHITECTURE §18.1).

Discoverable via the home-based default discover(); also importable directly:

    aivault import-file <api_conversation_history.json> --source cline
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
    first_user_title,
    to_iso,
)

# VS Code / VSCodium globalStorage locations for the Cline extension.
_CLINE_EXT = "globalStorage/saoudrizwan.claude-dev/tasks"


class ClineAdapter(SourceAdapter):
    source_type = "cline"
    source_kind = "local-log"
    home_subpaths = (
        f".config/Code/User/{_CLINE_EXT}",
        f".config/Code - OSS/User/{_CLINE_EXT}",
        f"AppData/Roaming/Code/User/{_CLINE_EXT}",
        f"Library/Application Support/Code/User/{_CLINE_EXT}",
    )
    file_glob = "**/api_conversation_history.json"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return []
        items = data if isinstance(data, list) else data.get("messages") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []

        messages: list[CanonicalMessage] = []
        commands: list[str] = []
        paths: list[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            role = it.get("role") or "document"
            content = it.get("content")
            body = content if isinstance(content, str) else extract_text(content)
            if not body:
                continue
            cmds, ps = extract_commands_and_paths(content)
            commands.extend(cmds)
            paths.extend(ps)
            messages.append(CanonicalMessage(role=str(role), content=body, created_at=to_iso(it.get("ts"))))
        if not messages:
            return []
        # task id is the parent dir name (…/tasks/<id>/api_conversation_history.json)
        sid = Path(original_path).parent.name if original_path else None
        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                source_session_id=sid,
                title=first_user_title(messages),
                messages=messages,
                commands=dedupe_keep_order(commands),
                file_paths=dedupe_keep_order(paths),
            )
        ]
