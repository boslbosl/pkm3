"""SourceAdapter interface + registry (ARCHITECTURE §6)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from ..models import CanonicalMessage, CanonicalSession, SourceCandidate
from ..platform_paths import home_dirs

# crude path-ish token used as a fallback to surface files mentioned in prose
_PATH_RE = re.compile(r"(?:[~./]|[A-Za-z]:\\)[\w./\\-]*\w\.\w{1,8}\b")


class SourceAdapter(ABC):
    """Each adapter discovers local sources and normalizes raw bytes.

    Adapters return normalized objects to the import engine; they must not
    write to the database.
    """

    source_type: str
    source_kind: str = "local-log"

    # Home-relative sub-paths to probe, e.g. (".claude/projects",). Adapters that
    # use the default home-based discovery just set this; others override discover.
    home_subpaths: tuple[str, ...] = ()
    file_glob: str = "**/*.jsonl"

    def discover(self, os_scope: str = "native") -> list[SourceCandidate]:
        """Locate candidate source dirs across OS contexts (ARCHITECTURE §8a).

        Default implementation composes ``home_subpaths`` onto each home dir
        returned for ``os_scope``. Adapters with no fixed location override this.
        """
        return candidates_from_homes(
            self.source_type, self.source_kind, self.home_subpaths, self.file_glob, os_scope
        )

    @abstractmethod
    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        """Parse raw bytes into one or more canonical sessions. Must tolerate
        malformed/unknown lines and never raise on bad input (ARCHITECTURE §18.1)."""


# ---------------------------------------------------------------------------
# Shared parsing helpers (used by the JSONL adapters)
# ---------------------------------------------------------------------------

def extract_text(content) -> str:
    """Normalize a message `content` that may be a str or a list of blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # text-bearing blocks across Claude/Codex shapes
                for key in ("text", "input_text", "output_text"):
                    if isinstance(block.get(key), str):
                        parts.append(block[key])
                        break
                else:
                    # tool_result content can itself be str or list
                    if block.get("type") == "tool_result":
                        parts.append(extract_text(block.get("content")))
        return "\n".join(p for p in parts if p)
    return str(content)


def extract_commands_and_paths(content) -> tuple[list[str], list[str]]:
    """Pull shell commands and file paths out of tool_use blocks + prose."""
    commands: list[str] = []
    paths: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            inp = block.get("input")
            if isinstance(inp, dict):
                cmd = inp.get("command")
                if isinstance(cmd, str) and cmd.strip():
                    commands.append(cmd.strip())
                for pk in ("file_path", "path", "notebook_path"):
                    val = inp.get(pk)
                    if isinstance(val, str) and val.strip():
                        paths.append(val.strip())
    # fallback: scan prose
    text = extract_text(content)
    for m in _PATH_RE.finditer(text):
        paths.append(m.group(0))
    return commands, paths


def candidates_from_homes(
    source_tool: str,
    source_kind: str,
    home_subpaths: tuple[str, ...],
    file_glob: str,
    os_scope: str,
) -> list[SourceCandidate]:
    """Build SourceCandidates by composing tool sub-paths onto each home dir."""
    out: list[SourceCandidate] = []
    if not home_subpaths:
        return out
    for home in home_dirs(os_scope):
        for sub in home_subpaths:
            root = home.path / sub
            try:
                if not root.exists():
                    continue
                count = sum(1 for _ in root.glob(file_glob))
            except (PermissionError, OSError):
                continue
            if count:
                out.append(
                    SourceCandidate(
                        source_tool=source_tool,
                        source_kind=source_kind,
                        path=root,
                        os_context=home.os_context,
                        estimated_sessions=count,
                    )
                )
    return out


def to_iso(ts) -> str | None:
    """Normalize a timestamp (epoch seconds or ISO string) to an ISO string."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(ts, str) and ts.strip():
        return ts
    return None


def first_user_title(messages: list[CanonicalMessage]) -> str | None:
    """First non-empty user message's first line, trimmed — a default title."""
    for m in messages:
        if m.role == "user" and m.content.strip():
            return m.content.strip().splitlines()[0][:80]
    return None


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _build_registry() -> dict[str, SourceAdapter]:
    # imported here to avoid circular imports at module load
    from .antigravity import AntigravityAdapter
    from .chatgpt import ChatGPTAdapter
    from .claude_code import ClaudeCodeAdapter
    from .claude_export import ClaudeExportAdapter
    from .cline import ClineAdapter
    from .codex import CodexAdapter
    from .cursor import CursorAdapter
    from .folder_import import FolderImportAdapter
    from .specstory import SpecStoryAdapter

    adapters: list[SourceAdapter] = [
        ClaudeCodeAdapter(),
        CodexAdapter(),
        AntigravityAdapter(),
        CursorAdapter(),
        ClineAdapter(),
        SpecStoryAdapter(),
        ChatGPTAdapter(),
        ClaudeExportAdapter(),
        FolderImportAdapter(),
    ]
    return {a.source_type: a for a in adapters}


registry: dict[str, SourceAdapter] = {}


def syncable_sources() -> list[str]:
    """Source tools that support auto-discovery (i.e. `aivault sync <tool>`),
    namely adapters that declare home-relative locations to scan."""
    out = []
    for tool, adapter in _build_registry().items():
        if getattr(adapter, "home_subpaths", ()):
            out.append(tool)
    return out


def get_adapter(source_tool: str) -> SourceAdapter:
    global registry
    if not registry:
        registry = _build_registry()
    if source_tool in registry:
        return registry[source_tool]
    # Unknown/web-export tools fall back to the generic folder importer,
    # but keep the user-supplied source_tool label.
    folder = registry["folder"]
    return _LabeledFolderAdapter(source_tool, folder)


class _LabeledFolderAdapter(SourceAdapter):
    """Wrap the folder importer so arbitrary --source labels are preserved."""

    def __init__(self, label: str, base: SourceAdapter):
        self.source_type = label
        self.source_kind = "manual"
        self._base = base

    def discover(self, os_scope: str = "native") -> list[SourceCandidate]:
        return []

    def normalize(self, raw_bytes: bytes, original_path: str | None) -> list[CanonicalSession]:
        sessions = self._base.normalize(raw_bytes, original_path)
        for s in sessions:
            s.source_tool = self.source_type
            s.source_kind = self.source_kind
        return sessions
