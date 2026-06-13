"""SpecStory adapter (PRD §7, near-term).

SpecStory saves chat history as Markdown under a workspace's
``.specstory/history/*.md``. Turns are delimited by role headers; this parser
handles the common ``_**User**_`` / ``_**Assistant**_`` markers and ``##``
headings, and tolerates files that don't match (one document message). Use:

    aivault import-file <.specstory/history/xxx.md> --source specstory
    aivault import-folder <.specstory/history> --source specstory
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import CanonicalMessage, CanonicalSession
from .base import SourceAdapter, first_user_title

# matches: _**User**_, **User**, ## User, ### Assistant, etc.
_ROLE_RE = re.compile(
    r"^\s*(?:_?\*\*|#{1,6}\s*)?\s*(user|human|assistant|ai|system)\b\s*(?:\*\*_?|:)?\s*$",
    re.IGNORECASE,
)
_ROLE_MAP = {"human": "user", "ai": "assistant"}


class SpecStoryAdapter(SourceAdapter):
    source_type = "specstory"
    source_kind = "markdown-folder"

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        text = raw_bytes.decode("utf-8", errors="replace")
        title = Path(original_path).stem if original_path else "specstory session"

        turns: list[tuple[str, list[str]]] = []
        current_role: str | None = None
        buf: list[str] = []

        def flush():
            if current_role is not None:
                body = "\n".join(buf).strip()
                if body:
                    turns.append((current_role, [body]))

        for line in text.splitlines():
            m = _ROLE_RE.match(line)
            if m:
                flush()
                role = m.group(1).lower()
                current_role = _ROLE_MAP.get(role, role)
                buf = []
            else:
                buf.append(line)
        flush()

        if not turns:
            # not a recognizable transcript — keep the whole doc as one message
            body = text.strip()
            if not body:
                return []
            messages = [CanonicalMessage(role="document", content=body)]
        else:
            messages = [CanonicalMessage(role=r, content=parts[0]) for r, parts in turns]

        return [
            CanonicalSession(
                source_tool=self.source_type,
                source_kind=self.source_kind,
                title=first_user_title(messages) or title,
                messages=messages,
            )
        ]
