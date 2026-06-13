# AIVault

**Local-first AI session collector, inbox, search, triage, and LLM Wiki export layer.**

AIVault collects and imports AI conversations and coding-agent sessions (Claude Code,
Codex, and more) into a local vault. It preserves the **raw evidence immutably**,
normalizes everything into one canonical session model, indexes it for fast search,
lets you triage what matters, and exports the keepers as LLM-Wiki / Obsidian–compatible
Markdown.

AIVault is **not** the final LLM Wiki — it is the source collection and curation layer
that feeds one. See `PRD.md`, `ARCHITECTURE.md`, and `START_HERE.md` for the canonical
v0.4 spec, and `task.md` for implementation status.

**v0.4** adds an Antigravity (IDE + CLI) adapter, cross-OS collection between WSL and
Windows, and a local web UI for browsing/searching the vault.

## Setup (uv)

This project is managed with [uv](https://docs.astral.sh/uv/). Dependencies are
installed into a project-local `.venv` from the committed `uv.lock` — nothing is
installed into your global/system Python.

```bash
uv sync          # create .venv and install deps (incl. the dev group)
```

Run any command inside the environment with `uv run` (no manual activation needed):

```bash
uv run aivault --help
```

## Quick start (vertical slice)

```bash
uv run aivault init ~/ai-vault
uv run aivault import-file ./tests/fixtures/claude-code-session.jsonl --source claude-code
uv run aivault list
uv run aivault search "refresh token"
uv run aivault show <session-id>
uv run aivault mark <session-id> wiki-ready
uv run aivault export llmwiki --status wiki-ready --out ./out/llmwiki
uv run aivault serve            # browse the vault at http://127.0.0.1:8765
```

The active vault is chosen by `--vault PATH`, then `$AIVAULT_HOME`, then `~/ai-vault`.

## Commands (MVP)

| Command | Purpose |
|---|---|
| `aivault init [path]` | Create a local vault (dirs + SQLite + config) |
| `aivault status` | Show vault location and counts |
| `aivault discover [--os-scope native\|windows\|wsl\|all]` | List local sources (optionally cross-OS) |
| `aivault sync claude-code` / `sync codex` / `sync antigravity` | Discover + import native logs (`--os-scope`) |
| `aivault import-file <path> --source <s>` | Import a single file |
| `aivault import-folder <path> --source <s>` | Import a folder of exports |
| `aivault list [--source] [--project] [--status]` | List sessions |
| `aivault search <query>` | Full-text search (FTS5) |
| `aivault show <session-id>` | Session detail |
| `aivault mark <session-id> <status>` | Set triage status |
| `aivault tag <session-id> <tag...>` | Add tags |
| `aivault export llmwiki --status wiki-ready --out <path>` | Export Markdown + manifest |
| `aivault serve [--host] [--port]` | Local web UI to browse/search the vault |

## Supported sources

Every tool below has a format-aware adapter. Import any single file with
`import-file --source <tool>` (or a directory with `import-folder`):

| `--source` | Tool | Input |
|---|---|---|
| `claude-code` | Claude Code | session `*.jsonl` |
| `codex` | Codex CLI/Desktop | rollout `*.jsonl` |
| `antigravity` | Antigravity (IDE + CLI) | agent `*.jsonl` |
| `cursor` | Cursor | exported conversation JSON/JSONL |
| `cline` | Cline | `api_conversation_history.json` |
| `specstory` | SpecStory | `.specstory/history/*.md` |
| `chatgpt` | ChatGPT | official export `.zip` or `conversations.json` |
| `claude` | Claude (web/desktop) | official export `.zip` or `conversations.json` |
| `folder` | anything else | `.md` / `.txt` / `.json` / `.html` (best-effort) |

```bash
uv run aivault import-file ./tests/fixtures/claude-code-session.jsonl --source claude-code
uv run aivault import-file ./tests/fixtures/codex-session.jsonl        --source codex
uv run aivault import-file ./tests/fixtures/antigravity-session.jsonl  --source antigravity
uv run aivault import-file ./tests/fixtures/cursor-session.json        --source cursor
uv run aivault import-file ./tests/fixtures/cline-task.json            --source cline
uv run aivault import-file ./tests/fixtures/specstory-history.md       --source specstory
uv run aivault import-file ./tests/fixtures/chatgpt-export.json        --source chatgpt
uv run aivault import-file ./tests/fixtures/claude-export.json         --source claude
```

`sync` auto-discovers local logs for tools with a known on-disk location
(`claude-code`, `codex`, `antigravity`, `cline`); the rest are imported from
their export files. Export-based adapters are best-effort and version-tolerant
(ARCHITECTURE §18.1).

## Web UI

`aivault serve` starts a dependency-free, local-only web app (default
`http://127.0.0.1:8765`) for browsing the vault three ways — by project/repo, by
source tool, and as a chronological timeline — with shared FTS search and a
detail panel that shows **all** session metadata. Read-only in v0.4.

## Cross-OS collection (WSL ↔ Windows)

`--os-scope` selects where discovery looks: `native` (current OS), `windows`
(Windows user profiles, incl. `/mnt/<drive>/Users/*` from WSL), `wsl` (distro
homes, incl. `\\wsl.localhost\<distro>\home\*` from Windows), or `all`. Each
session records its `os_context` so the two sides never silently merge.

## Tests

```bash
uv run pytest
```

## Stack

Python 3.11+ · Typer · Pydantic · SQLite + FTS5 · pytest.
