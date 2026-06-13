"""Vault location resolution and on-disk layout (ARCHITECTURE §4).

Vault is global by default (`~/ai-vault`), overridable via `--vault` or
`$AIVAULT_HOME` (ARCHITECTURE §18, decision 5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import __version__

CONFIG_FILENAME = "config.yaml"
DB_RELPATH = "db/aivault.sqlite"

# Directory layout created by `aivault init`.
VAULT_DIRS = (
    "raw/artifacts/claude-code",
    "raw/artifacts/codex",
    "raw/artifacts/antigravity",
    "raw/artifacts/chatgpt",
    "raw/artifacts/claude",
    "raw/artifacts/cursor",
    "raw/artifacts/cline",
    "raw/artifacts/specstory",
    "raw/artifacts/folder",
    "raw/artifacts/cass",
    "raw/manifests",
    "db",
    "exports/llmwiki",
    "exports/obsidian",
    "exports/jsonl",
    "inbox/capsules",
    "logs",
)

DEFAULT_VAULT = Path.home() / "ai-vault"


def resolve_vault_path(explicit: str | os.PathLike | None = None) -> Path:
    """Resolve which vault to use: explicit > $AIVAULT_HOME > ~/ai-vault."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("AIVAULT_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_VAULT.resolve()


@dataclass
class VaultConfig:
    root: Path
    version: str = __version__
    default_sensitivity: str = "unknown"
    redaction_policy: str = "warn"  # warn | block | mask | off

    @property
    def db_path(self) -> Path:
        return self.root / DB_RELPATH

    @property
    def config_path(self) -> Path:
        return self.root / CONFIG_FILENAME

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw" / "artifacts"

    def exists(self) -> bool:
        return self.config_path.exists()

    # --- persistence -----------------------------------------------------
    def save(self) -> None:
        data = {
            "version": self.version,
            "root": str(self.root),
            "default_sensitivity": self.default_sensitivity,
            "redaction_policy": self.redaction_policy,
        }
        self.config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @classmethod
    def load(cls, root: Path) -> "VaultConfig":
        cfg_path = root / CONFIG_FILENAME
        if not cfg_path.exists():
            raise FileNotFoundError(
                f"No vault at {root}. Run `aivault init {root}` first."
            )
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return cls(
            root=root,
            version=data.get("version", __version__),
            default_sensitivity=data.get("default_sensitivity", "unknown"),
            redaction_policy=data.get("redaction_policy", "warn"),
        )


def create_vault_dirs(root: Path) -> None:
    for rel in VAULT_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
