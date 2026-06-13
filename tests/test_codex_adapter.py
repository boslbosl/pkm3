from aivault.adapters.codex import CodexAdapter


def test_parses_meta_and_messages(codex_fixture):
    sessions = CodexAdapter().normalize(codex_fixture.read_bytes(), str(codex_fixture))
    assert len(sessions) == 1
    s = sessions[0]
    assert s.source_tool == "codex"
    assert s.source_session_id == "codex-sess-77"
    assert s.project_name == "api-svc"
    assert s.started_at == "2026-06-11T14:00:00Z"
    # user + assistant + trailing flat user message; function_call skipped
    roles = [m.role for m in s.messages]
    assert roles == ["user", "assistant", "user"]
    assert "idempotent" in s.messages[0].content


def test_handles_flat_message_shape(codex_fixture):
    s = CodexAdapter().normalize(codex_fixture.read_bytes(), str(codex_fixture))[0]
    assert s.messages[-1].content == "Looks good, also add a rollback step"


def test_import_via_vault(vault, codex_fixture):
    res = vault.import_file(codex_fixture, "codex")
    assert len(res.imported) == 1
