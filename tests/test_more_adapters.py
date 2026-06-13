"""Adapters for the remaining supported agents (cursor, cline, specstory,
chatgpt export, claude export)."""

import io
import zipfile
from pathlib import Path

import pytest

from aivault.adapters.chatgpt import ChatGPTAdapter
from aivault.adapters.claude_export import ClaudeExportAdapter
from aivault.adapters.cline import ClineAdapter
from aivault.adapters.cursor import CursorAdapter
from aivault.adapters.specstory import SpecStoryAdapter

FIX = Path(__file__).parent / "fixtures"


# --- cursor ----------------------------------------------------------------

def test_cursor_export_json():
    f = FIX / "cursor-session.json"
    s = CursorAdapter().normalize(f.read_bytes(), str(f))[0]
    assert s.source_tool == "cursor"
    assert s.title == "Fix flaky login test"
    assert [m.role for m in s.messages] == ["user", "assistant"]
    assert "test_login" in s.messages[0].content


# --- cline -----------------------------------------------------------------

def test_cline_task_history():
    f = FIX / "cline-task.json"
    # simulate the real path so the task id (parent dir) is captured
    path = "/home/u/.config/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/1699999999999/api_conversation_history.json"
    s = ClineAdapter().normalize(f.read_bytes(), path)[0]
    assert s.source_tool == "cline"
    assert s.source_session_id == "1699999999999"
    assert [m.role for m in s.messages] == ["user", "assistant", "user"]
    assert "npm test" in s.commands
    assert "All tests passed" in s.messages[2].content


# --- specstory -------------------------------------------------------------

def test_specstory_markdown_turns():
    f = FIX / "specstory-history.md"
    s = SpecStoryAdapter().normalize(f.read_bytes(), str(f))[0]
    assert s.source_tool == "specstory"
    roles = [m.role for m in s.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert "CORS" in s.messages[0].content


def test_specstory_non_transcript_is_single_doc():
    s = SpecStoryAdapter().normalize(b"just some notes, no roles", "notes.md")[0]
    assert len(s.messages) == 1
    assert s.messages[0].role == "document"


# --- chatgpt export --------------------------------------------------------

def test_chatgpt_export_json_multiple_conversations():
    f = FIX / "chatgpt-export.json"
    sessions = ChatGPTAdapter().normalize(f.read_bytes(), str(f))
    # second conversation is system-only with empty text -> dropped
    assert len(sessions) == 1
    s = sessions[0]
    assert s.source_session_id == "cg-1"
    assert s.title == "Summarize abstract"
    assert [m.role for m in s.messages] == ["user", "assistant"]
    assert s.started_at is not None  # epoch create_time converted to ISO


def test_chatgpt_export_from_zip():
    f = FIX / "chatgpt-export.json"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("conversations.json", f.read_bytes())
    sessions = ChatGPTAdapter().normalize(buf.getvalue(), "chatgpt-export.zip")
    assert len(sessions) == 1
    assert sessions[0].messages[1].role == "assistant"


# --- claude export ---------------------------------------------------------

def test_claude_export_json():
    f = FIX / "claude-export.json"
    s = ClaudeExportAdapter().normalize(f.read_bytes(), str(f))[0]
    assert s.source_tool == "claude"
    assert s.source_session_id == "cl-1"
    assert s.title == "Plan a trip to Rome"
    assert [m.role for m in s.messages] == ["user", "assistant"]  # human -> user
    assert s.started_at == "2026-05-01T10:00:00Z"


# --- vault round-trip for every new source --------------------------------

@pytest.mark.parametrize(
    "fixture,source,expected_sessions",
    [
        ("cursor-session.json", "cursor", 1),
        ("cline-task.json", "cline", 1),
        ("specstory-history.md", "specstory", 1),
        ("chatgpt-export.json", "chatgpt", 1),
        ("claude-export.json", "claude", 1),
    ],
)
def test_import_via_vault(vault, fixture, source, expected_sessions):
    res = vault.import_file(FIX / fixture, source)
    assert len(res.imported) == expected_sessions
    rows = vault.list_sessions(source=source)
    assert len(rows) == expected_sessions


def test_all_registered_sources_resolve():
    from aivault.adapters.base import _build_registry

    reg = _build_registry()
    for tool in ("claude-code", "codex", "antigravity", "cursor", "cline",
                 "specstory", "chatgpt", "claude", "folder"):
        assert tool in reg
