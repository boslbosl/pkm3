def test_os_context_persisted_and_filterable(vault, claude_fixture):
    res = vault.import_file(claude_fixture, "claude-code", os_context="windows")
    assert len(res.imported) == 2

    win = vault.list_sessions(os_context="windows")
    assert len(win) == 2
    assert all(r["os_context"] == "windows" for r in win)

    # raw artifact also records the cross-OS context
    art = vault.conn.execute("SELECT os_context FROM raw_artifacts").fetchone()
    assert art["os_context"] == "windows"

    assert vault.list_sessions(os_context="native") == []


def test_default_context_is_inferred_native(vault, codex_fixture):
    vault.import_file(codex_fixture, "codex")  # local tmp path -> native
    rows = vault.list_sessions(source="codex")
    assert rows[0]["os_context"] in ("native", "wsl")  # depends on test host
