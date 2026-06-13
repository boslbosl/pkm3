"""Source adapters. Adapters normalize raw bytes into CanonicalSession objects
and never touch the database (ARCHITECTURE §6)."""

from __future__ import annotations

from .antigravity import AntigravityAdapter
from .base import SourceAdapter, get_adapter, registry
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .folder_import import FolderImportAdapter

__all__ = [
    "SourceAdapter",
    "get_adapter",
    "registry",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "AntigravityAdapter",
    "FolderImportAdapter",
]
