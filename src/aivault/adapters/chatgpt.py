"""ChatGPT official export adapter (PRD §7, near-term).

The OpenAI data export is a ``.zip`` containing ``conversations.json``: a list
of conversations, each with a ``mapping`` of message nodes. This adapter accepts
either the ``.zip`` or the ``conversations.json`` directly, and yields one
CanonicalSession per conversation. Version-tolerant (ARCHITECTURE §18.1). Use:

    aivault import-file <chatgpt-export.zip> --source chatgpt
"""

from __future__ import annotations

import io
import json
import zipfile

from ..models import CanonicalMessage, CanonicalSession
from .base import SourceAdapter, first_user_title, to_iso

_VALID_ROLES = {"user", "assistant", "system", "tool"}


class ChatGPTAdapter(SourceAdapter):
    source_type = "chatgpt"
    source_kind = "official-export"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        data = _load_conversations(raw_bytes)
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
        mapping = conv.get("mapping")
        rows: list[tuple[float, str, str]] = []  # (sort_key, role, text)
        if isinstance(mapping, dict):
            for i, node in enumerate(mapping.values()):
                if not isinstance(node, dict):
                    continue
                msg = node.get("message")
                if not isinstance(msg, dict):
                    continue
                role = (msg.get("author") or {}).get("role")
                if role not in _VALID_ROLES:
                    continue
                text = _parts_text(msg.get("content"))
                if not text:
                    continue
                rows.append((msg.get("create_time") or i, role, text))
        rows.sort(key=lambda r: r[0])
        messages = [CanonicalMessage(role=r, content=t) for _, r, t in rows]
        if not messages:
            return None
        return CanonicalSession(
            source_tool=self.source_type,
            source_kind=self.source_kind,
            source_session_id=conv.get("conversation_id") or conv.get("id"),
            title=conv.get("title") or first_user_title(messages),
            started_at=to_iso(conv.get("create_time")),
            ended_at=to_iso(conv.get("update_time")),
            messages=messages,
        )


def _parts_text(content) -> str:
    """Extract text from a ChatGPT message content object."""
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            return "\n".join(p for p in parts if isinstance(p, str) and p)
        if isinstance(content.get("text"), str):
            return content["text"]
    if isinstance(content, str):
        return content
    return ""


def _load_conversations(raw_bytes: bytes):
    """Return parsed conversations.json data from a zip or raw JSON, else None."""
    if raw_bytes[:2] == b"PK":  # zip signature
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                name = next(
                    (n for n in zf.namelist() if n.endswith("conversations.json")), None
                )
                if name is None:
                    return None
                raw_bytes = zf.read(name)
        except (zipfile.BadZipFile, KeyError, OSError):
            return None
    try:
        return json.loads(raw_bytes.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return None
