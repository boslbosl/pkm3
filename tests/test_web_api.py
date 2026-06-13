from aivault.web import api


def _seed(vault, claude_fixture, codex_fixture):
    vault.import_file(claude_fixture, "claude-code")
    vault.import_file(codex_fixture, "codex")


def test_stats_breakdowns(vault, claude_fixture, codex_fixture):
    _seed(vault, claude_fixture, codex_fixture)
    s = api.stats(vault)
    assert s["sessions"] == 3
    assert s["by_source"]["claude-code"] == 2
    assert s["by_source"]["codex"] == 1
    assert "by_status" in s and "by_os" in s


def test_group_by_project(vault, claude_fixture, codex_fixture):
    _seed(vault, claude_fixture, codex_fixture)
    data = api.list_sessions(vault, group="project")
    assert data["group_by"] == "project"
    labels = {g["label"] for g in data["groups"]}
    # cwd basenames from the fixtures
    assert {"myrepo", "other", "api-svc"} <= labels


def test_group_by_source_and_time(vault, claude_fixture, codex_fixture):
    _seed(vault, claude_fixture, codex_fixture)
    by_source = api.list_sessions(vault, group="source")
    assert any("claude-code" in g["label"] for g in by_source["groups"])

    timeline = api.list_sessions(vault, group="time")
    assert len(timeline["groups"]) == 1
    assert timeline["groups"][0]["key"] == "timeline"
    assert len(timeline["groups"][0]["sessions"]) == 3


def test_search_filters_list(vault, claude_fixture, codex_fixture):
    _seed(vault, claude_fixture, codex_fixture)
    data = api.list_sessions(vault, group="time", q="migration")
    sessions = data["groups"][0]["sessions"] if data["groups"] else []
    assert len(sessions) == 1
    assert sessions[0]["source_tool"] == "codex"


def test_session_detail_exposes_all_metadata(vault, claude_fixture):
    res = vault.import_file(claude_fixture, "claude-code")
    sid = res.imported[0]
    d = api.session_detail(vault, sid)
    for key in (
        "id", "source_tool", "os_context", "project_name", "project_root",
        "status", "sensitivity", "content_hash", "dedupe_key",
        "source_fingerprint", "raw_artifact", "messages", "tags",
        "commands", "files", "redaction_findings",
    ):
        assert key in d
    assert d["raw_artifact"]["stored_path"].startswith("raw/artifacts/claude-code/")
    assert len(d["messages"]) == d["message_count"]


def test_session_detail_missing_returns_none(vault):
    assert api.session_detail(vault, "does-not-exist") is None
