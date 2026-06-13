"""Cursor adapter (PRD §7, near-term).

Cursor keeps chats in a local SQLite ``state.vscdb`` that is awkward to read
directly, so this adapter targets **exported** conversations (JSON or JSONL),
which is the portable path. Version-tolerant per ARCHITECTURE §18.1. Use:

    aivault import-file <cursor-export.json> --source cursor
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


class CursorAdapter(SourceAdapter):
    source_type = "cursor"
    source_kind = "export"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        items, title = _load(text)
        messages: list[CanonicalMessage] = []
        commands: list[str] = []
        paths: list[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            role = it.get("role") or it.get("type") or "document"
            content = it.get("content")
            if content is None:
                content = it.get("text") or it.get("message")
            body = content if isinstance(content, str) else extract_text(content)
            if not body:
                continue
            cmds, ps = extract_commands_and_paths(content)
            commands.extend(cmds)
            paths.extend(ps)
            messages.append(
                CanonicalMessage(role=str(role), content=body, created_at=to_iso(it.get("timestamp")))
            )
        if not messages:
            return []
        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                title=title or first_user_title(messages),
                messages=messages,
                commands=dedupe_keep_order(commands),
                file_paths=dedupe_keep_order(paths),
            )
        ]


def _load(text: str) -> tuple[list, str | None]:
    """Return (message-items, title) from a JSON doc, list, or JSONL."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # JSONL fallback: one message object per line
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
        return items, None

    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        for key in ("messages", "conversation", "items", "history"):
            if isinstance(data.get(key), list):
                return data[key], data.get("title") or data.get("name")
    return [], None
