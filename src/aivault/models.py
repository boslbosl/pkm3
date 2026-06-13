"""Canonical Pydantic models shared across adapters and services.

Adapters return these objects; the import engine is responsible for persistence.
Adapters MUST NOT write to the database (ARCHITECTURE §6).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

# Allowed triage statuses (PRD §6.4 / ARCHITECTURE §11).
STATUSES = ("new", "reviewed", "keep", "ignore", "wiki_ready", "exported")

SENSITIVITIES = ("unknown", "public", "internal", "confidential", "secret")


class CanonicalMessage(BaseModel):
    role: str
    content: str = ""
    created_at: str | None = None
    meta: dict = Field(default_factory=dict)


class CanonicalSession(BaseModel):
    source_tool: str
    source_kind: str
    source_session_id: str | None = None
    title: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    project_name: str | None = None
    project_root: str | None = None
    summary: str | None = None
    sensitivity: str = "unknown"
    messages: list[CanonicalMessage] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)


class SourceCandidate(BaseModel):
    """A discovered local source location (PRD §6.1)."""

    source_tool: str
    source_kind: str
    path: Path
    os_context: str = "native"
    estimated_sessions: int = 0
