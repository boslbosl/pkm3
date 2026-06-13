"""Source adapters. Adapters normalize raw bytes into CanonicalSession objects
and never touch the database (ARCHITECTURE §6)."""

from __future__ import annotations

from .antigravity import AntigravityAdapter
from .base import SourceAdapter, get_adapter, registry
from .chatgpt import ChatGPTAdapter
from .claude_code import ClaudeCodeAdapter
from .claude_export import ClaudeExportAdapter
from .cline import ClineAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .folder_import import FolderImportAdapter
from .specstory import SpecStoryAdapter

__all__ = [
    "SourceAdapter",
    "get_adapter",
    "registry",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "AntigravityAdapter",
    "CursorAdapter",
    "ClineAdapter",
    "SpecStoryAdapter",
    "ChatGPTAdapter",
    "ClaudeExportAdapter",
    "FolderImportAdapter",
]
