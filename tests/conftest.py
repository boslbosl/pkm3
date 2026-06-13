from __future__ import annotations

from pathlib import Path

import pytest

from aivault.service import init_vault, open_vault

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "ai-vault"
    init_vault(root)
    _cfg, v = open_vault(root)
    yield v
    v.close()


@pytest.fixture
def claude_fixture() -> Path:
    return FIXTURES / "claude-code-session.jsonl"


@pytest.fixture
def codex_fixture() -> Path:
    return FIXTURES / "codex-session.jsonl"
