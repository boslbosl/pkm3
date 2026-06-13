"""Generic folder/file import adapter (ARCHITECTURE §7.3).

Best-effort fallback for Markdown / TXT / JSON / HTML exports from browser
tools or official exports not yet covered by a native adapter. One file -> one
session. Source tool is set by the caller (`--source`); kind is "manual".
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from ..models import CanonicalMessage, CanonicalSession, SourceCandidate
from .base import SourceAdapter

_TAG_RE = re.compile(r"<[^>]+>")


class FolderImportAdapter(SourceAdapter):
    source_type = "folder"
    source_kind = "manual"

    def discover(self) -> list[SourceCandidate]:
        # Generic importer has no fixed discovery location.
        return []

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        suffix = (Path(original_path).suffix.lower() if original_path else "")
        title = Path(original_path).stem if original_path else "imported session"

        if suffix == ".json":
            messages = self._from_json(text)
        elif suffix in (".html", ".htm"):
            messages = [CanonicalMessage(role="document", content=self._strip_html(text))]
        else:  # .md .txt and everything else: treat as one document
            messages = [CanonicalMessage(role="document", content=text)]

        if not messages:
            return []
        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                source_session_id=None,
                title=title,
                messages=messages,
            )
        ]

    @staticmethod
    def _from_json(text: str) -> list[CanonicalMessage]:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return [CanonicalMessage(role="document", content=text)]

        # common shapes: {"messages":[{role,content}]} or a bare list
        items = None
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            items = data["messages"]
        elif isinstance(data, list):
            items = data
        if items is None:
            return [CanonicalMessage(role="document", content=json.dumps(data, indent=2))]

        msgs: list[CanonicalMessage] = []
        for it in items:
            if isinstance(it, dict) and ("content" in it or "text" in it):
                content = it.get("content")
                if not isinstance(content, str):
                    content = it.get("text", "")
                msgs.append(
                    CanonicalMessage(role=str(it.get("role", "document")), content=str(content))
                )
        return msgs or [CanonicalMessage(role="document", content=json.dumps(data, indent=2))]

    @staticmethod
    def _strip_html(text: str) -> str:
        no_tags = _TAG_RE.sub(" ", text)
        return html.unescape(re.sub(r"\s+", " ", no_tags)).strip()
