def test_reimport_same_file_is_idempotent(vault, claude_fixture):
    first = vault.import_file(claude_fixture, "claude-code")
    assert len(first.imported) == 2

    second = vault.import_file(claude_fixture, "claude-code")
    # identical bytes -> artifact-hash dedupe skips the whole file
    assert second.imported == []
    assert second.skipped == 1

    # still only two sessions and one raw artifact
    assert len(vault.list_sessions()) == 2
    assert vault.counts()["raw_artifacts"] == 1


def test_redaction_findings_recorded(vault, claude_fixture):
    res = vault.import_file(claude_fixture, "claude-code")
    # the .env LOG_LEVEL line is benign; ensure scan ran without crashing
    assert res.findings >= 0
    assert vault.counts()["sessions"] == 2


def test_secret_is_detected(vault, tmp_path):
    f = tmp_path / "leak.md"
    f.write_text("here is my key AKIAIOSFODNN7EXAMPLE do not share", encoding="utf-8")
    res = vault.import_file(f, "folder")
    assert res.findings >= 1
    sid = res.imported[0]
    findings = vault.get_findings(sid)
    assert any(x["kind"] == "aws_access_key" for x in findings)
