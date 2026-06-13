"""Dedupe keys (ARCHITECTURE §9).

source_fingerprint = source_tool + original_path + source_session_id
content_hash       = sha256(normalized_message_text)
artifact_hash      = sha256(raw_file_bytes)
export_hash        = sha256(exported_markdown_body)
"""

from __future__ import annotations

import hashlib

from .models import CanonicalSession


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def artifact_hash(raw_bytes: bytes) -> str:
    return sha256_bytes(raw_bytes)


def source_fingerprint(source_tool: str, original_path: str | None, source_session_id: str | None) -> str:
    basis = "|".join([source_tool, original_path or "", source_session_id or ""])
    return sha256_text(basis)


def content_hash(session: CanonicalSession) -> str:
    normalized = "\n".join(f"{m.role}:{m.content.strip()}" for m in session.messages)
    return sha256_text(normalized)


def export_hash(markdown_body: str) -> str:
    return sha256_text(markdown_body)
