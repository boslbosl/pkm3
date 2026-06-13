# task.md — AIVault Implementation Tasks

**Spec:** Canonical v0.3 (`PRD.md`, `ARCHITECTURE.md`, `START_HERE.md`)
**Goal of milestone 1:** prove the vertical slice end-to-end before any UI/LLM/broad adapters.

```text
Claude Code / Codex JSONL
  -> import into immutable raw store
  -> normalize into Session/Message
  -> index with SQLite FTS5
  -> triage (mark wiki_ready)
  -> export LLM Wiki Markdown (+ manifest)
```

Status legend: `[x]` done · `[~]` in progress · `[ ]` todo

---

## Phase 0 — Project skeleton
- [x] `pyproject.toml` (Python 3.11+, Typer, Pydantic, hatchling; `aivault` console script)
- [x] `src/aivault/` package layout per START_HERE §7
- [x] `README.md`, `.gitignore`
- [x] Resolve ARCHITECTURE §17 open decisions (see §18)

## Phase 1 — Local vault foundation
- [x] `config.py` — vault resolution (`--vault` / `AIVAULT_HOME` / `~/ai-vault`), `config.yaml`, dir layout
- [x] `db.py` — SQLite connection + FTS5 schema/migrations
- [x] `raw_store.py` — immutable artifact copy + SHA-256
- [x] `dedupe.py` — artifact_hash / content_hash / source_fingerprint
- [x] `models.py` — Pydantic canonical models
- [x] `aivault init` / `aivault status`

## Phase 2 — Native coding-agent adapters
- [x] `adapters/base.py` — `SourceAdapter` interface + registry
- [x] `adapters/claude_code.py` — JSONL (version-tolerant)
- [x] `adapters/codex.py` — JSONL (version-tolerant)
- [x] `adapters/folder_import.py` — md/txt/json/html fallback
- [x] `aivault import-file` / `import-folder`
- [x] `aivault discover` / `sync claude-code` / `sync codex`
- [ ] Cline / Cursor / SpecStory adapters (post-MVP)

## Phase 3 — Search and session view
- [x] FTS5 indexing of title/prompts/responses/commands/file_paths/summary/notes
- [x] `aivault search <query>`
- [x] `aivault show <session-id>`
- [x] `aivault list [--source] [--project] [--status]`

## Phase 4 — Triage workflow
- [x] status field + state validation (`new`,`reviewed`,`keep`,`ignore`,`wiki_ready`,`exported`)
- [x] `aivault mark <id> <status>`
- [x] `aivault tag <id> <tag...>`
- [x] notes support
- [x] basic redaction detection (`redaction.py`, findings table)

## Phase 5 — LLM Wiki export
- [x] `exporters/llmwiki.py` — frontmatter + body sections + raw-evidence link
- [x] export manifest (`manifest.json`)
- [x] idempotent re-export (export_hash)
- [x] `aivault export llmwiki --status wiki-ready --out <path>`
- [ ] `exporters/obsidian.py`, `exporters/jsonl.py` (post-MVP)

## Phase 6 — Web/export sources (post-MVP)
- [ ] ChatGPT export zip, Claude export, Pactify/Notion folders, Perplexity

## Phase 7 — Optional CASS bridge (post-MVP)
- [ ] `adapters/cass_bridge.py` (subprocess; raw-store backfill only)

## Tests
- [x] `tests/fixtures/` — Claude Code + Codex JSONL fixtures
- [x] `test_claude_code_adapter.py`
- [x] `test_codex_adapter.py`
- [x] `test_dedupe.py`
- [x] `test_llmwiki_export.py` (incl. idempotency)
- [x] `conftest.py` — temp vault fixture

## MVP acceptance (START_HERE §8)
- [x] `aivault init` creates a local vault
- [x] Claude Code + Codex sessions discoverable/importable
- [x] raw evidence preserved
- [x] normalized common schema
- [x] search across sessions
- [x] mark `wiki_ready`
- [x] `export llmwiki` produces Markdown w/ metadata + raw refs
- [x] re-running sync/import does not duplicate
