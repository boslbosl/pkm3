"""Config-driven sync: persisted sync_sources, syncable detection."""

from aivault.adapters.base import syncable_sources
from aivault.config import VaultConfig
from aivault.service import init_vault, open_vault


def test_syncable_sources_are_discoverable_agents():
    s = set(syncable_sources())
    # adapters that declare home_subpaths
    assert {"claude-code", "codex", "antigravity", "cline"} <= s
    # export-only adapters are NOT auto-syncable
    assert "cursor" not in s
    assert "chatgpt" not in s
    assert "folder" not in s


def test_config_sync_sources_round_trip(tmp_path):
    root = tmp_path / "v"
    init_vault(root)

    cfg = VaultConfig.load(root)
    assert cfg.sync_sources == []          # default empty
    assert cfg.sync_os_scope == "native"

    cfg.sync_sources = ["claude-code", "codex"]
    cfg.sync_os_scope = "all"
    cfg.save()

    reloaded = VaultConfig.load(root)
    assert reloaded.sync_sources == ["claude-code", "codex"]
    assert reloaded.sync_os_scope == "all"


def test_detect_groups_by_tool(tmp_path, monkeypatch):
    # Make discovery deterministic regardless of the test host: inject a fake home
    # tree containing a Claude Code session.
    import aivault.adapters.base as base
    from aivault.platform_paths import HomeDir

    fake_home = tmp_path / "home"
    proj = fake_home / ".claude" / "projects" / "repo"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text('{"type":"user","sessionId":"x","message":{"role":"user","content":"hi"}}\n')

    # base.py imported home_dirs by name, so patch it there
    monkeypatch.setattr(base, "home_dirs", lambda scope: [HomeDir(fake_home, "native")])

    root = tmp_path / "vault"
    init_vault(root)
    _cfg, v = open_vault(root)
    try:
        found = v.detect("native")
    finally:
        v.close()

    assert "claude-code" in found
    assert found["claude-code"]["sessions"] >= 1
    assert "native" in found["claude-code"]["os_contexts"]
