from aivault.adapters.claude_code import ClaudeCodeAdapter


def test_parses_multiple_sessions_and_skips_malformed(claude_fixture):
    sessions = ClaudeCodeAdapter().normalize(
        claude_fixture.read_bytes(), str(claude_fixture)
    )
    assert len(sessions) == 2
    s1 = sessions[0]
    assert s1.source_tool == "claude-code"
    assert s1.source_session_id == "cc-sess-001"
    assert s1.project_name == "myrepo"
    assert s1.title == "Add JWT refresh token rotation to auth.py"
    assert s1.started_at == "2026-06-10T09:00:00Z"
    assert s1.ended_at == "2026-06-10T09:01:10Z"
    # 4 messages in session 1
    assert len(s1.messages) == 4
    assert s1.messages[0].role == "user"

    # session 2 has no summary -> title falls back to its own first user message,
    # not session 1's summary (leafUuid-based mapping, not positional)
    s2 = sessions[1]
    assert s2.source_session_id == "cc-sess-002"
    assert s2.title == "Quick question about logging config"


def test_extracts_commands_and_file_paths(claude_fixture):
    s1 = ClaudeCodeAdapter().normalize(claude_fixture.read_bytes(), str(claude_fixture))[0]
    assert "pytest tests/test_auth.py -q" in s1.commands
    assert "/home/dev/myrepo/auth.py" in s1.file_paths


def test_tool_result_content_is_extracted(claude_fixture):
    s1 = ClaudeCodeAdapter().normalize(claude_fixture.read_bytes(), str(claude_fixture))[0]
    tool_result_msg = s1.messages[2]
    assert "2 passed" in tool_result_msg.content


def test_import_via_vault(vault, claude_fixture):
    res = vault.import_file(claude_fixture, "claude-code")
    assert len(res.imported) == 2
    rows = vault.list_sessions()
    assert len(rows) == 2
