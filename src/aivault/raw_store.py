"""Immutable raw artifact store (ARCHITECTURE §4, principle 2).

Original files are copied verbatim into `raw/artifacts/<source>/` and never
mutated. Generated/exported files live outside `raw/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import VaultConfig
from .dedupe import artifact_hash

# source_tool -> raw/artifacts subdir. Unknown tools fall back to "folder".
_KNOWN_BUCKETS = {
    "claude-code",
    "codex",
    "antigravity",
    "chatgpt",
    "claude",
    "cursor",
    "cline",
    "specstory",
    "folder",
    "cass",
}


@dataclass
class StoredArtifact:
    stored_rel_path: str  # relative to vault root
    stored_abs_path: Path
    artifact_hash: str
    bytes: int


def _bucket(source_tool: str) -> str:
    return source_tool if source_tool in _KNOWN_BUCKETS else "folder"


def store_artifact(
    cfg: VaultConfig, source_tool: str, original_path: str | None, raw_bytes: bytes
) -> StoredArtifact:
    """Copy raw bytes into the vault, named by content hash (collision-free, idempotent)."""
    digest = artifact_hash(raw_bytes)
    suffix = Path(original_path).suffix if original_path else ".bin"
    bucket = _bucket(source_tool)
    dest_dir = cfg.raw_dir / bucket
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{digest}{suffix}"
    if not dest.exists():
        dest.write_bytes(raw_bytes)
    rel = dest.relative_to(cfg.root).as_posix()
    return StoredArtifact(
        stored_rel_path=rel,
        stored_abs_path=dest,
        artifact_hash=digest,
        bytes=len(raw_bytes),
    )
