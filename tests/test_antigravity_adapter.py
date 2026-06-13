from pathlib import Path

from aivault.adapters.antigravity import AntigravityAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "antigravity-session.jsonl"


def test_parses_mixed_shapes_and_skips_malformed():
    sessions = AntigravityAdapter().normalize(FIXTURE.read_bytes(), str(FIXTURE))
    assert len(sessions) == 1
    s = sessions[0]
    assert s.source_tool == "antigravity"
    assert s.source_session_id == "ag-001"
    assert s.project_name == "webapp"
    assert s.project_root == "/home/dev/webapp"
    roles = [m.role for m in s.messages]
    assert roles == ["user", "assistant", "user"]
    assert s.messages[0].content.startswith("Build a REST endpoint")
    assert "add pagination too" == s.messages[-1].content


def test_extracts_file_path():
    s = AntigravityAdapter().normalize(FIXTURE.read_bytes(), str(FIXTURE))[0]
    assert "/home/dev/webapp/app.py" in s.file_paths


def test_import_via_vault(vault):
    res = vault.import_file(FIXTURE, "antigravity")
    assert len(res.imported) == 1
    rows = vault.list_sessions(source="antigravity")
    assert rows[0]["project_root"] == "/home/dev/webapp"
