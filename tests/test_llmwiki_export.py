import json

from aivault.exporters.llmwiki import export_llmwiki


def _import_and_mark(vault, fixture):
    res = vault.import_file(fixture, "claude-code")
    sid = res.imported[0]
    vault.mark(sid, "wiki-ready")
    return sid


def test_export_produces_markdown_and_manifest(vault, claude_fixture, tmp_path):
    sid = _import_and_mark(vault, claude_fixture)
    out = tmp_path / "llmwiki"
    summary = export_llmwiki(vault, out, status="wiki-ready")

    assert len(summary.exported) == 1
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["count"] == 1
    item = manifest["items"][0]
    assert item["session_id"] == sid

    md_file = out / item["out_file"]
    assert md_file.exists()
    text = md_file.read_text()
    assert text.startswith("---")
    assert "source_tool: claude-code" in text
    assert "## Goal" in text
    assert "## Raw evidence" in text
    assert "raw/artifacts/claude-code/" in text


def test_only_exports_matching_status(vault, claude_fixture, tmp_path):
    vault.import_file(claude_fixture, "claude-code")  # left as 'new'
    out = tmp_path / "llmwiki"
    summary = export_llmwiki(vault, out, status="wiki-ready")
    assert summary.exported == []
    assert json.loads((out / "manifest.json").read_text())["count"] == 0


def test_reexport_is_idempotent(vault, claude_fixture, tmp_path):
    _import_and_mark(vault, claude_fixture)
    out = tmp_path / "llmwiki"

    first = export_llmwiki(vault, out, status="wiki-ready")
    assert len(first.exported) == 1

    second = export_llmwiki(vault, out, status="wiki-ready")
    assert second.exported == []   # unchanged content
    assert second.skipped == 1
