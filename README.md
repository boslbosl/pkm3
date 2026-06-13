# AIVault

**Local-first AI session collector, inbox, search, triage, and LLM Wiki export layer.**

AIVault collects and imports AI conversations and coding-agent sessions (Claude Code,
Codex, and more) into a local vault. It preserves the **raw evidence immutably**,
normalizes everything into one canonical session model, indexes it for fast search,
lets you triage what matters, and exports the keepers as LLM-Wiki / Obsidian–compatible
Markdown.

AIVault is **not** the final LLM Wiki — it is the source collection and curation layer
that feeds one. See `PRD.md`, `ARCHITECTURE.md`, and `START_HERE.md` for the canonical
v0.3 spec, and `task.md` for implementation status.

## Install (dev)

```bash
pip install -e ".[dev]"
```

## Quick start (vertical slice)

```bash
aivault init ~/ai-vault
aivault import-file ./tests/fixtures/claude-code-session.jsonl --source claude-code
aivault list
aivault search "refresh token"
aivault show <session-id>
aivault mark <session-id> wiki-ready
aivault export llmwiki --status wiki-ready --out ./out/llmwiki
```

The active vault is chosen by `--vault PATH`, then `$AIVAULT_HOME`, then `~/ai-vault`.

## Commands (MVP)

| Command | Purpose |
|---|---|
| `aivault init [path]` | Create a local vault (dirs + SQLite + config) |
| `aivault status` | Show vault location and counts |
| `aivault discover` | List supported local sources found on this machine |
| `aivault sync claude-code` / `sync codex` | Discover + import native logs |
| `aivault import-file <path> --source <s>` | Import a single file |
| `aivault import-folder <path> --source <s>` | Import a folder of exports |
| `aivault list [--source] [--project] [--status]` | List sessions |
| `aivault search <query>` | Full-text search (FTS5) |
| `aivault show <session-id>` | Session detail |
| `aivault mark <session-id> <status>` | Set triage status |
| `aivault tag <session-id> <tag...>` | Add tags |
| `aivault export llmwiki --status wiki-ready --out <path>` | Export Markdown + manifest |

## Tests

```bash
pytest
```

## Stack

Python 3.11+ · Typer · Pydantic · SQLite + FTS5 · pytest.
