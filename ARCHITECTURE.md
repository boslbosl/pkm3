# ARCHITECTURE — AIVault

**Version:** Canonical v0.3  
**Date:** 2026-06-12  
**Scope:** Local-first AI session collection, normalization, search, triage, and export.

---

## 1. System context

AIVault sits between AI tools and downstream knowledge systems.

```text
[AI tools and exports]
  ChatGPT / Claude / Perplexity
  Codex / Claude Code / Cursor / Cline / SpecStory
  Official exports / browser exports / CASS exports / manual folders
        │
        ▼
[AIVault]
  discover -> import -> raw store -> normalize -> index -> triage -> export
        │
        ├── CLI
        ├── local web UI, later
        ├── MCP/API, later
        ├── LLM Wiki export
        ├── Obsidian export
        └── JSONL/Notion-ready export
```

AIVault is the collection and curation layer, not the final wiki compiler.

---

## 2. Architecture principles

1. **Local-first:** all data stays local unless the user explicitly exports or syncs.
2. **Raw evidence is immutable:** generated summaries never overwrite source files.
3. **Canonical schema:** every tool is normalized into the same session/message model.
4. **Adapters are replaceable:** source-specific parsing lives outside core logic.
5. **Idempotent sync:** re-running imports must not create duplicates.
6. **Review before export:** not every raw session should become wiki material.
7. **Compatibility over fork:** integrate with CASS and LLM Wiki tools without making them core dependencies.

---

## 3. High-level components

```text
┌──────────────────────────────────────────────────────────────┐
│ Interfaces                                                    │
│ CLI │ Local Web UI later │ MCP/API later                      │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Application Services                                          │
│ source mgmt │ sync jobs │ search │ triage │ redaction │ export│
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Core Services                                                 │
│ Import Engine │ Normalizer │ Dedupe │ Redaction │ Project Map │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Storage                                                       │
│ raw artifacts │ SQLite metadata │ messages │ FTS index         │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Outputs                                                       │
│ LLM Wiki Markdown │ Obsidian │ JSONL │ Notion-ready │ manifests│
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Vault layout

Recommended vault directory:

```text
ai-vault/
  config.yaml
  raw/
    artifacts/
      claude-code/
      codex/
      chatgpt/
      claude/
      cursor/
      cline/
      folder/
      cass/
    manifests/
  db/
    aivault.sqlite
  exports/
    llmwiki/
    obsidian/
    jsonl/
  inbox/
    capsules/
  logs/
```

`raw/` is immutable. Exported and generated files live outside raw.

---

## 5. Storage model

Use SQLite for MVP.

### Tables

```text
sources
import_batches
raw_artifacts
sessions
messages
snippets
attachments
projects
tags
session_tags
export_runs
export_items
redaction_findings
```

### FTS

Use SQLite FTS5 tables for:

- session title
- user prompts
- assistant responses
- command snippets
- file paths
- extracted summaries
- user notes

---

## 6. Adapter interface

Each adapter implements:

```python
class SourceAdapter:
    source_type: str

    def discover(self) -> list[SourceCandidate]:
        ...

    def import_source(self, candidate: SourceCandidate) -> list[RawArtifact]:
        ...

    def normalize(self, artifact: RawArtifact) -> list[CanonicalSession]:
        ...
```

Adapters must not write directly to the database. They return normalized objects to the import engine.

---

## 7. MVP adapters

### 7.1 Claude Code adapter

Input:

- JSONL session logs
- optional manually exported Markdown/text

Output:

- one `RawArtifact` per session file
- one `Session`
- many `Message` rows
- extracted tool calls, file paths, commands where possible

---

### 7.2 Codex adapter

Input:

- local JSONL session logs
- WSL and native filesystem paths

Output:

- same canonical model as Claude Code

---

### 7.3 Folder import adapter

Input:

- Markdown, JSON, TXT, HTML files from browser/export tools

Output:

- best-effort sessions
- raw artifact preservation
- source tool set by user or inferred from file metadata

---

## 8. CASS bridge

CASS is optional.

AIVault may call CASS via subprocess when installed:

```bash
cass sessions --json
cass search "query" --robot
cass export <session> --format markdown
cass export <session> --format json
```

Bridge rules:

1. CASS output is imported as raw evidence or normalized source data.
2. AIVault does not use the CASS DB as its internal source of truth.
3. AIVault does not copy CASS source code into MVP.
4. If CASS is unavailable, native adapters continue to work.

---

## 9. Dedupe strategy

Use multiple keys:

```text
source_fingerprint = source_tool + original_path + source_session_id
content_hash       = sha256(normalized_message_text)
artifact_hash      = sha256(raw_file_bytes)
export_hash        = sha256(exported_markdown_body)
```

Duplicate handling:

- exact artifact hash match: skip import
- same source fingerprint: update metadata, preserve original artifact
- similar content hash: create duplicate group for review

---

## 10. Redaction strategy

MVP redaction is detection-first.

Detect:

- API keys and tokens
- private keys
- passwords
- `.env` fragments
- database URLs
- emails and personal identifiers, optional
- local filesystem paths, optional

Workflow:

```text
import -> detect findings -> show preview -> export blocks or masks findings based on policy
```

Default export behavior should warn on high-confidence secrets.

---

## 11. Triage state machine

```text
new -> reviewed -> keep -> wiki_ready -> exported
  \       \         \
   \       \         -> ignore
    \       -> ignore
     -> ignore
```

Allowed statuses:

- `new`
- `reviewed`
- `keep`
- `ignore`
- `wiki_ready`
- `exported`

---

## 12. LLM Wiki export format

Output example:

```text
exports/llmwiki/raw/sessions/<project>/<date>_<source>_<slug>.md
exports/llmwiki/manifest.json
```

Markdown frontmatter:

```yaml
---
source_tool: claude-code
source_kind: local-log
project: myrepo
session_id: abc123
started_at: 2026-06-12T21:00:00+09:00
status: wiki_ready
raw_artifact: raw/artifacts/claude-code/abc123.jsonl
dedupe_key: sha256:...
sensitivity: internal
---
```

Body sections:

```markdown
# Session title

## Goal

## Key outcome

## Important decisions

## Files and commands

## Conversation excerpts

## Open questions

## Raw evidence
```

MVP can export raw excerpts without LLM-generated summaries. Capsule generation can be added later.

---

## 13. CLI commands

MVP CLI:

```bash
aivault init [path]
aivault status
aivault discover
aivault sync claude-code
aivault sync codex
aivault import-file <path> --source <source>
aivault import-folder <path> --source <source>
aivault list [--source] [--project] [--status]
aivault search <query>
aivault show <session-id>
aivault mark <session-id> <status>
aivault tag <session-id> <tag...>
aivault export llmwiki --status wiki-ready --out <path>
```

Later CLI:

```bash
aivault cass discover
aivault cass import
aivault redact preview
aivault capsule generate
aivault serve
aivault mcp serve
```

---

## 14. Suggested implementation stack

```text
Python 3.11+
Typer for CLI
Pydantic for canonical models
SQLite + FTS5 for storage/search
pytest for test fixtures
watchdog later for file watching
FastAPI + React/Tauri later for local UI
```

---

## 15. First vertical slice

Build this first:

```text
fixture Claude Code JSONL
  -> raw artifact copy
  -> parse messages
  -> insert session/messages
  -> FTS search
  -> mark wiki_ready
  -> export Markdown
```

Repository tasks:

1. Create project skeleton.
2. Create SQLite schema migrations.
3. Implement raw store.
4. Implement `SourceAdapter` base interface.
5. Implement Claude Code JSONL parser from fixture.
6. Implement session list/show/search CLI.
7. Implement triage status command.
8. Implement LLM Wiki Markdown exporter.
9. Add dedupe tests.
10. Add export snapshot tests.

---

## 16. Deployment model

MVP is a local CLI tool.

No daemon required.

Later:

- local web UI
- file watcher service
- tray app
- MCP server
- optional encrypted vault
- optional cloud sync

---

## 17. Open design decisions

1. Whether to use Python-only or TypeScript + Python split.
2. Whether to store messages only in SQLite or also as normalized JSONL files.
3. Whether to generate session capsules via local LLM, hosted LLM, or no LLM in MVP.
4. How much Cursor and Cline support to ship in MVP versus using CASS/folder import first.
5. Whether vault should live globally or per-project by default.

---

## 18. Resolved MVP decisions

These resolve §17 for the first implementation so coding can begin. They are MVP
choices, not permanent constraints.

| # | Decision | Resolution for MVP | Rationale |
|---|---|---|---|
| 1 | Language | **Python 3.11+ only** | Best filesystem/parsing ergonomics; simple CASS subprocess bridge later. TS/Tauri UI deferred to post-MVP. |
| 2 | Message storage | **SQLite only** (raw file stays immutable in `raw/`) | Single source of truth; normalized JSONL export can be added as an exporter, not a second store. |
| 3 | Capsule generation | **No LLM in MVP** | Export raw excerpts + extracted commands/files. Capsule (`Goal`, `Key outcome`, …) sections are emitted with best-effort heuristics and left for later LLM enrichment. |
| 4 | Cursor / Cline | **Deferred** | MVP ships Claude Code + Codex native adapters and a generic folder importer as the fallback for everything else. |
| 5 | Vault location | **Global by default** (`~/ai-vault`), overridable via `--vault` or `AIVAULT_HOME` | Sessions span many projects; a single vault avoids fragmentation. |

### 18.1 Adapter robustness requirement

Coding-agent JSONL formats drift between tool versions (field renames, content as
`str` vs. list-of-blocks, summary/meta lines, tool-call wrappers). All native
adapters MUST:

- parse **line-by-line and tolerate malformed/unknown lines** (skip, never crash);
- normalize `content` whether it is a plain string or a list of typed blocks
  (`text`, `input_text`, `output_text`, `tool_use`, `tool_result`);
- treat session id / cwd / timestamps as **optional** and fall back gracefully;
- be covered by a fixture in `tests/fixtures/` representing the expected shape.
