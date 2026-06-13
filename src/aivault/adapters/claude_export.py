"""Claude official export adapter (PRD §7, near-term).

The Anthropic/Claude data export is a ``conversations.json`` (optionally inside a
``.zip``): a list of conversations, each with ``chat_messages`` whose ``sender``
is ``human`` / ``assistant``. Yields one CanonicalSession per conversation.
Version-tolerant (ARCHITECTURE §18.1). Distinct from the ``claude-code`` adapter.

    aivault import-file <claude-export.zip|conversations.json> --source claude
"""

from __future__ import annotations

import io
import json
import zipfile

from ..models import CanonicalMessage, CanonicalSession
from .base import SourceAdapter, extract_text, first_user_title, to_iso

_SENDER_MAP = {"human": "user", "assistant": "assistant"}


class ClaudeExportAdapter(SourceAdapter):
    source_type = "claude"
    source_kind = "official-export"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        data = _load(raw_bytes)
        if data is None:
            return []
        conversations = data if isinstance(data, list) else data.get("conversations", [])
        sessions: list[CanonicalSession] = []
        for conv in conversations:
            if isinstance(conv, dict):
                s = self._convert(conv)
                if s:
                    sessions.append(s)
        return sessions

    def _convert(self, conv: dict) -> CanonicalSession | None:
        chat = conv.get("chat_messages")
        if not isinstance(chat, list):
            return None
        messages: list[CanonicalMessage] = []
        for m in chat:
            if not isinstance(m, dict):
                continue
            sender = m.get("sender") or m.get("role") or "document"
            role = _SENDER_MAP.get(sender, sender)
            text = m.get("text")
            if not text:
                text = extract_text(m.get("content"))
            if not text:
                continue
            messages.append(
                CanonicalMessage(role=role, content=text, created_at=to_iso(m.get("created_at")))
            )
        if not messages:
            return None
        return CanonicalSession(
            source_tool=self.source_type,
            source_kind=self.source_kind,
            source_session_id=conv.get("uuid") or conv.get("id"),
            title=conv.get("name") or conv.get("title") or first_user_title(messages),
            started_at=to_iso(conv.get("created_at")),
            ended_at=to_iso(conv.get("updated_at")),
            messages=messages,
        )


def _load(raw_bytes: bytes):
    if raw_bytes[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                name = next((n for n in zf.namelist() if n.endswith("conversations.json")), None)
                if name is None:
                    return None
                raw_bytes = zf.read(name)
        except (zipfile.BadZipFile, KeyError, OSError):
            return None
    try:
        return json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return None
