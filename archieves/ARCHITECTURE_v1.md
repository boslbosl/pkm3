# ARCHITECTURE.md — AI Session Vault

**Version:** 0.2  
**Date:** 2026-06-12  
**Working name:** AI Session Vault / AIVault  
**Status:** Draft architecture for MVP

---

## 1. Architecture summary

AIVault is a local-first session collection and knowledge-preparation system. It ingests AI chat and coding-agent histories from multiple sources, normalizes them into a canonical local schema, indexes them for search, supports review/triage, and exports selected sessions into an LLM Wiki-compatible structure.

The architecture separates four layers:

1. **Source layer** — vendor logs, official exports, CASS output, folder exports, manual files.
2. **Canonical vault layer** — immutable raw store, normalized metadata, message store, search index.
3. **Review layer** — inbox, source health, dedupe groups, redaction, wiki-ready queue.
4. **Output layer** — LLM Wiki export, Obsidian export, Notion-ready export, optional MCP/API.

```text
┌─────────────────────────────────────────────────────────────┐
│ Source Layer                                                │
│ Claude Code │ Codex │ Cursor │ Cline │ ChatGPT │ Claude │ ...│
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Adapter Layer                                               │
│ Native adapters │ Official export parsers │ CASS bridge     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Canonical Vault                                             │
│ raw store │ SQLite metadata │ message store │ FTS index      │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Review + Preparation                                        │
│ inbox │ dedupe │ redaction │ capsule │ wiki-ready queue     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Output Layer                                                │
│ llm-wiki export │ Obsidian │ JSONL │ Notion-ready │ MCP/API │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Design principles

### 2.1 Local-first

All source data, normalized data, indexes, and exports live locally by default. Network operations are explicit opt-in.

### 2.2 Raw evidence is immutable

Raw logs and exports are never edited in place. AIVault either references original paths or copies them into `raw/` with hashes.

### 2.3 Canonical schema owns product logic

Each adapter maps source-specific formats into AIVault's canonical schema. Downstream features must depend on the canonical schema, not vendor-specific formats.

### 2.4 CASS is a bridge, not the database of record

CASS may be used to discover and export coding-agent sessions, but AIVault stores its own normalized session records, import batches, statuses, redaction flags, and export manifests.

### 2.5 Export is controlled by review state

No source is exported to the LLM Wiki by default. Sessions must pass review or be explicitly marked `wiki-ready`.

### 2.6 Compatibility-first, not fork-first

AIVault should be compatible with CASS, SpecStory, Pratiyush/llm-wiki, Obsidian, and Notion, but should not fork those projects as its core.

---

## 3. Major components

### 3.1 CLI app

Primary interface for MVP.

Commands:

```bash
aivault init
aivault sources discover
aivault sources list
aivault sources enable <source>
aivault sources doctor
aivault sync [source]
aivault import <path> --source <source>
aivault search <query>
aivault inbox list
aivault session show <id>
aivault session mark <id> <status>
aivault session capsule <id>
aivault export llmwiki
aivault cass doctor
aivault cass sync
aivault doctor
```

### 3.2 Local web UI

P1 component, optional for MVP.

Pages:

- Dashboard
- Source health
- Import batches
- Inbox
- Session detail
- Project view
- Duplicate groups
- Redaction preview
- Export queue
- Settings

### 3.3 Source registry

Stores configured sources, paths, adapter type, OS context, source health, and last sync state.

Example:

```yaml
sources:
  claude_code_wsl:
    adapter: claude_code
    context: wsl
    root: \\wsl$\Ubuntu\home\user\.claude\projects
    enabled: true
  codex_windows:
    adapter: codex
    context: windows
    root: C:\Users\user\.codex\sessions
    enabled: true
  cass:
    adapter: cass_bridge
    executable: cass
    enabled: true
```

### 3.4 Adapter layer

Adapter responsibilities:

1. Discover source availability.
2. Enumerate candidate raw sessions.
3. Parse or request normalized content.
4. Compute content hash and dedupe key.
5. Emit canonical `Session`, `Message`, `ToolCall`, `FileRef`, and `RawRef` records.
6. Report parse errors and source health.

Adapter interface:

```python
class SourceAdapter:
    id: str
    display_name: str

    def discover(self) -> list[DiscoveredSource]: ...
    def health(self, source: SourceConfig) -> SourceHealth: ...
    def enumerate(self, source: SourceConfig) -> Iterable[RawCandidate]: ...
    def parse(self, candidate: RawCandidate) -> ParsedSession: ...
```

### 3.5 CASS bridge adapter

The CASS bridge treats CASS as an external executable.

It should use only JSON/robot-mode outputs, never the interactive TUI.

Planned command usage:

```bash
cass triage --json
cass capabilities --json
cass sessions --workspace <path> --json --limit <n>
cass sessions --current --json
cass search <query> --robot --limit <n> --fields minimal
cass view <source_path> -n <line> --json
cass expand <source_path> -n <line> -C <context> --json
cass export <source_path> --format markdown -o <output.md>
cass export <source_path> --format json --include-tools
cass timeline --since 7d --json
cass sources list --json
cass sources sync --json
```

Bridge responsibilities:

- Detect CASS installation and version.
- Run `cass triage --json` before other commands.
- Reject or warn on unsupported output schema versions.
- Import sessions exported by CASS into AIVault's canonical schema.
- Preserve original source paths and CASS provenance.
- Never rely on CASS as the only copy of indexed metadata.

CASS integration modes:

| Mode | Description | MVP recommendation |
|---|---|---:|
| `disabled` | No CASS integration. | Supported |
| `bridge` | Invoke installed CASS CLI and parse JSON/Markdown outputs. | Default if CASS exists |
| `import-folder` | Import a folder of CASS exports. | Supported |
| `vendor` | Bundle or copy CASS code. | Not recommended |
| `fork` | Fork CASS as product base. | Not recommended |

### 3.6 Native adapters

MVP native adapters:

- `claude_code`
- `codex`
- `chatgpt_export`
- `claude_export`
- `generic_markdown`
- `generic_jsonl`
- `specstory`

P1 native adapters:

- `cursor`
- `cline`
- `perplexity_export`
- `notion_export`

### 3.7 Raw store

The raw store preserves imported evidence.

Two modes:

1. **Copy mode:** copy raw file/export into `raw/` and hash it.
2. **Reference mode:** store original path, hash, and metadata without copying full content.

MVP default:

- Copy official exports and manually imported files.
- Reference large local vendor stores by default.
- Allow `--copy-raw` for complete archival.

### 3.8 Metadata database

SQLite database under `.aivault/aivault.db`.

Primary tables:

- `sources`
- `import_batches`
- `raw_refs`
- `sessions`
- `messages`
- `tool_calls`
- `file_refs`
- `projects`
- `capsules`
- `redaction_findings`
- `duplicate_groups`
- `export_manifests`

### 3.9 Search index

MVP:

- SQLite FTS5 over sessions and messages.

P1:

- Optional local embeddings.
- Optional hybrid search.
- Topic clustering.

### 3.10 Review/triage engine

Maintains session statuses:

```text
raw → needs-review → reviewed → wiki-ready → exported
                  ↘ ignored
```

Rules:

- Imported sessions start as `raw` or `needs-review`.
- Sessions with redaction hits start as `needs-review`.
- Only `wiki-ready` sessions are exported by default.
- `ignored` sessions remain searchable only if user permits.

### 3.11 Capsule generator

Generates a session capsule Markdown file from a session.

Capsule sections:

1. Goal
2. Outcome
3. Decisions
4. Files touched or inspected
5. Commands run
6. Errors and fixes
7. Open questions
8. Follow-ups
9. Raw evidence references

MVP implementation:

- Template-based extraction without LLM by default.
- Optional LLM generation through configured provider.

### 3.12 Exporters

MVP exporters:

- `llmwiki`
- `obsidian`
- `jsonl`
- `markdown-folder`

P1 exporters:

- `notion-ready`
- `mcp-docs`
- `static-site-manifest`

---

## 4. Vault layout

Recommended default layout:

```text
ai-vault/
  raw/
    imports/
      chatgpt/
      claude/
      perplexity/
    agents/
      claude-code/
      codex/
      cursor/
      cline/
    folders/
    cass/
  inbox/
    capsules/
  wiki-export/
    llmwiki/
    obsidian/
  .aivault/
    aivault.db
    config.yaml
    source_state/
    logs/
    cache/
    manifests/
```

Generated files should be separated from immutable raw evidence:

```text
raw/          immutable or source-referenced evidence
inbox/        review and capsule workspace
wiki-export/  deterministic downstream export
.aivault/     internal database, cache, config, logs
```

---

## 5. Canonical schema

### 5.1 Session table

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  source_tool TEXT NOT NULL,
  source_adapter TEXT NOT NULL,
  source_context TEXT,
  source_id TEXT,
  source_path TEXT,
  source_hash TEXT,
  dedupe_key TEXT,
  title TEXT,
  project_id TEXT,
  workspace_path TEXT,
  started_at TEXT,
  ended_at TEXT,
  captured_at TEXT NOT NULL,
  status TEXT NOT NULL,
  sensitivity TEXT DEFAULT 'unknown',
  message_count INTEGER DEFAULT 0,
  tool_call_count INTEGER DEFAULT 0,
  file_ref_count INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 5.2 Message table

```sql
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  role TEXT NOT NULL,
  timestamp TEXT,
  content_text TEXT,
  content_json TEXT,
  source_line INTEGER,
  redaction_state TEXT DEFAULT 'unchecked',
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### 5.3 Tool call table

```sql
CREATE TABLE tool_calls (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  message_id TEXT,
  ordinal INTEGER,
  tool_name TEXT,
  input_json TEXT,
  output_text TEXT,
  status TEXT,
  created_at TEXT,
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### 5.4 Raw refs table

```sql
CREATE TABLE raw_refs (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  raw_uri TEXT NOT NULL,
  raw_kind TEXT NOT NULL,
  content_hash TEXT,
  copied_to TEXT,
  source_adapter TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);
```

### 5.5 Import batches table

```sql
CREATE TABLE import_batches (
  id TEXT PRIMARY KEY,
  source_id TEXT,
  adapter TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  candidates_seen INTEGER DEFAULT 0,
  sessions_new INTEGER DEFAULT 0,
  sessions_updated INTEGER DEFAULT 0,
  sessions_skipped INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  manifest_json TEXT
);
```

---

## 6. Source adapters

### 6.1 Claude Code adapter

Input:

- Local JSONL transcripts from Claude Code session directories.
- Optional `/export` plain-text files.

Parsing:

- Each JSONL line becomes message, tool call, or metadata.
- Project is inferred from encoded working directory path or transcript metadata.

Special handling:

- Windows and WSL paths are separate source contexts.
- `CLAUDE_CONFIG_DIR` override must be supported.
- Path mapping must preserve original path and local resolved path.

### 6.2 Codex adapter

Input:

- Local Codex CLI sessions.
- Codex resume/fork session IDs when discoverable.
- Optional Desktop export or manually exported logs.

Parsing:

- Session JSONL or event stream records become messages/tool calls.
- Workspace directory is used for project mapping when available.

Special handling:

- Windows and WSL are separate source contexts.
- Desktop and CLI histories may not be unified; preserve source surface.

### 6.3 Cursor adapter

MVP stance:

- Prefer CASS bridge or generic Cursor export folder.

P1 native adapter:

- Discover VS Code-style workspace/global storage.
- Parse SQLite `state.vscdb` variants.
- Handle large DBs and WAL files read-only.

### 6.4 Cline adapter

MVP stance:

- Prefer CASS bridge or Cline export/generic folder import.

P1 native adapter:

- Discover VS Code global storage task directories.
- Parse task metadata, messages, token usage, and timeline if available.

### 6.5 ChatGPT export adapter

Input:

- Official ChatGPT data export ZIP.
- `conversations.json` and related files.

Parsing:

- Each exported conversation becomes one session.
- Messages are reconstructed from exported conversation tree where possible.

### 6.6 Claude export adapter

Input:

- Official Claude data export ZIP.

Parsing:

- Each exported conversation becomes one session.
- Projects, attachments, and metadata are preserved when present.

### 6.7 Generic folder adapter

Input:

- Markdown, TXT, JSON, JSONL, HTML, or ZIP files.

Use cases:

- Perplexity manual exports.
- AI Exporter outputs.
- AI Toolbox outputs.
- Pactify/Notion exports.
- SpecStory Markdown histories.

---

## 7. CASS bridge detail

### 7.1 Why bridge to CASS

CASS already discovers and indexes many local coding-agent histories. For AIVault, it can accelerate MVP support for:

- Claude Code
- Codex
- Cursor
- Cline
- Gemini CLI
- Aider
- GitHub Copilot Chat
- other agent stores supported by CASS

### 7.2 What CASS provides

AIVault can use CASS for:

- source discovery;
- health/triage;
- listing sessions;
- keyword search;
- current workspace session lookup;
- context expansion around search hits;
- Markdown/JSON export;
- remote SSH sync, if the user already uses it;
- provenance fields for remote/local sources.

### 7.3 What CASS does not provide for AIVault

AIVault still needs its own:

- import batch table;
- review states;
- secret redaction workflow;
- duplicate grouping across official exports, manual exports, and CASS;
- session capsules;
- LLM Wiki export manifests;
- web AI export ingestion;
- Notion/folder import;
- stable product UI.

### 7.4 Bridge data flow

```text
cass source stores
  ~/.claude/projects
  ~/.codex/sessions
  Cursor state.vscdb
  Cline task dirs
        │
        ▼
CASS index/search/export
        │  JSON/Markdown only
        ▼
AIVault cass_bridge adapter
        │
        ▼
AIVault canonical DB + raw refs
        │
        ▼
inbox / search / redaction / llmwiki export
```

### 7.5 Bridge failure modes

| Failure | Handling |
|---|---|
| `cass` not installed | Source health = `not_configured`; suggest native adapters/imports. |
| Bare `cass` would launch TUI | Never run bare `cass`; use `--json`/`--robot`. |
| Output schema changes | Version gate and schema validation. |
| CASS index stale | Run or recommend `cass index --full` or `cass triage --json` next command. |
| CASS unsupported source | Fall back to native adapter or generic import. |
| License/redistribution risk | Do not vendor; user-installed external bridge only. |

---

## 8. Dedupe strategy

A session can arrive through multiple routes:

- vendor local log;
- CASS export;
- official account export;
- browser extension export;
- manual Markdown copy;
- Notion export.

Dedupe key candidates:

```text
1. vendor session ID, if available
2. normalized source path + file hash
3. first user message hash + start timestamp + source tool
4. title + message count + content simhash
5. CASS source_path + CASS source_id + source line range
```

Duplicate group states:

- `exact_duplicate`
- `same_session_different_format`
- `possible_duplicate`
- `not_duplicate`

Default action:

- Preserve all raw refs.
- Create one canonical session if confidence is high.
- Keep duplicate group visible for review.

---

## 9. Redaction architecture

### 9.1 Detection

MVP detection uses deterministic regex/pattern scanning:

- API keys
- bearer tokens
- SSH keys
- private keys
- database URLs
- `.env` secrets
- cloud credentials
- emails, optional
- local paths, optional

### 9.2 Redaction states

```text
unchecked → flagged → reviewed-safe
                    ↘ redacted
                    ↘ blocked
```

### 9.3 Export gate

Rules:

- Sessions with `blocked` findings cannot be exported.
- Sessions with `flagged` findings require `--allow-flagged` or manual review.
- Redacted exports must retain a pointer to raw evidence, but raw evidence itself should not be copied to public export targets unless explicitly allowed.

---

## 10. Path and source-context mapping

### 10.1 Problem

The same project may appear as:

```text
C:\Users\me\dev\project
\\wsl$\Ubuntu\home\me\dev\project
/home/me/dev/project
/Users/me/dev/project
```

### 10.2 Model

```yaml
path_mappings:
  - source_context: wsl
    from: /home/me/dev
    to: C:\Users\me\dev-wsl-mirror
    project_root: project
  - source_context: windows
    from: C:\Users\me\dev
    to: /mnt/c/Users/me/dev
```

### 10.3 Rules

- Preserve original path always.
- Store resolved local path separately.
- Project identity should be stable even if path differs by OS context.
- Do not assume Windows and WSL histories are the same source.

---

## 11. LLM Wiki exporter

### 11.1 Directory layout

```text
wiki-export/llmwiki/
  raw/
    sessions/
      <project>/
        <date>_<source>_<slug>.md
  inbox/
    capsules/
      <date>_<source>_<project>_<slug>.md
  manifests/
    export_<timestamp>.json
```

### 11.2 Markdown frontmatter

```yaml
---
aivault_id: sess_01J...
source_tool: claude-code
source_adapter: cass-bridge
source_context: wsl
project: myrepo
workspace_path_original: /home/me/dev/myrepo
started_at: 2026-06-12T10:30:00+09:00
captured_at: 2026-06-12T11:05:00+09:00
status: wiki-ready
sensitivity: internal
raw_refs:
  - raw_uri: ~/.claude/projects/.../session.jsonl
    hash: sha256:...
redaction_status: reviewed-safe
---
```

### 11.3 Content structure

```md
# <Session title>

## Summary

## Goal

## Outcome

## Decisions

## Files referenced or changed

## Commands and tool calls

## Errors and resolutions

## Follow-ups

## Raw evidence

## Transcript excerpt or full transcript
```

### 11.4 Export manifest

Each export writes a manifest:

```json
{
  "export_id": "exp_...",
  "created_at": "2026-06-12T12:00:00+09:00",
  "filter": {"status": "wiki-ready"},
  "session_count": 42,
  "files_written": [...],
  "redaction_policy": "block-flagged",
  "aivault_version": "0.2.0"
}
```

---

## 12. Security and privacy

### 12.1 Threats

- Secrets leaked into exports.
- Sensitive customer data copied to wiki.
- Prompt injection embedded in raw transcripts.
- Vendor log format confusion leading to incorrect attribution.
- Accidental publication of raw transcripts.

### 12.2 Controls

- Local-only default.
- Read-only source access.
- Redaction preview.
- Export gates by status.
- Raw/wikified separation.
- Explicit opt-in for LLM summarization.
- Export manifest and provenance.
- `.gitignore` defaults for raw and internal DB.

Default `.gitignore`:

```gitignore
.aivault/
raw/
*.db
*.sqlite
*.sqlite3
*.env
```

---

## 13. Process model

### 13.1 Sync process

```text
for each enabled source:
  health check
  enumerate candidates
  hash candidate
  skip if unchanged
  parse candidate
  normalize records
  run redaction scan
  compute dedupe key
  insert/update canonical DB
  update FTS index
  record import batch result
```

### 13.2 Export process

```text
select sessions by status/filter
validate redaction status
load capsule or generate draft
render Markdown
write deterministic file path
write export manifest
mark exported if requested
```

---

## 14. API boundaries

### 14.1 Internal service modules

```text
core.config
core.sources
core.raw_store
core.parser
core.schema
core.dedupe
core.redaction
core.index
core.inbox
core.capsules
core.exporters
core.cass_bridge
```

### 14.2 CLI to core

The CLI should call internal service functions directly in MVP.

### 14.3 Web UI to core

P1 local web UI should call a local HTTP API:

```text
GET  /api/sources
POST /api/sync
GET  /api/sessions
GET  /api/sessions/{id}
POST /api/sessions/{id}/mark
POST /api/sessions/{id}/capsule
POST /api/export/llmwiki
```

### 14.4 MCP server

P1/P2 MCP tools:

```text
search_sessions(query, project?, source?, limit?)
get_session(session_id)
get_capsule(session_id)
list_recent_sessions(project?, days?)
export_context_pack(query, max_tokens?)
```

---

## 15. Suggested technology stack

### 15.1 MVP

- Language: Python 3.11+
- CLI: Typer or Click
- DB: SQLite + FTS5
- Config: YAML/TOML
- Parsing: standard library + pydantic models
- Packaging: uv or pipx-compatible package
- Tests: pytest

### 15.2 P1 web UI

- Backend: FastAPI
- Frontend: React + TanStack Table or lightweight HTMX
- Local auth: loopback-only by default
- Optional desktop shell: Tauri later

### 15.3 Why not Rust for MVP

Rust would be appropriate for a high-performance search/indexer like CASS. AIVault's MVP risk is adapter/product workflow complexity rather than raw performance. Python allows faster parser iteration and easier integration with export formats.

---

## 16. Testing strategy

### 16.1 Unit tests

- Parser fixtures for each source type.
- Dedupe key stability.
- Redaction patterns.
- Export renderer snapshots.
- Path mapping normalization.

### 16.2 Integration tests

- Import sample ChatGPT export ZIP.
- Import sample Claude export ZIP.
- Import Claude Code JSONL fixture.
- Import Codex JSONL fixture.
- Bridge to mocked CASS JSON output.
- Export LLM Wiki fixture and compare snapshots.

### 16.3 Safety tests

- Secrets are flagged before export.
- Blocked sessions cannot export.
- Raw files are not modified.
- Duplicate imports preserve raw refs.

---

## 17. Migration and versioning

### 17.1 DB migrations

Use explicit migration files:

```text
.aivault/migrations/
  0001_initial.sql
  0002_add_capsules.sql
  0003_add_cass_bridge.sql
```

### 17.2 Adapter versions

Each parsed session records:

```yaml
adapter_name: claude_code
adapter_version: 0.2.0
parser_schema_version: 1
```

This enables reparsing when vendor formats change.

---

## 18. Deployment modes

### 18.1 Single-user local CLI

Default MVP mode.

```bash
pipx install aivault
aivault init ~/ai-vault
```

### 18.2 Repo-local mode

For project-specific vaults:

```bash
aivault init .ai-vault --repo-local
```

### 18.3 Team vault mode

P2.

- Shared Git repository.
- Raw excluded or encrypted.
- Capsules and wiki exports reviewed by PR.

---

## 19. Implementation roadmap

### Phase 1 — Skeleton

- CLI app
- Config
- SQLite schema
- Vault layout
- Generic folder import
- Search

### Phase 2 — Priority imports

- Claude Code adapter
- Codex adapter
- ChatGPT export adapter
- Claude export adapter

### Phase 3 — CASS bridge

- CASS discovery
- CASS health/triage
- CASS sessions import
- CASS export import
- CASS provenance fields

### Phase 4 — Triage and export

- Inbox statuses
- Redaction scan
- Capsule template
- LLM Wiki exporter
- Export manifest

### Phase 5 — UI and intelligence

- Local web UI
- Native Cursor adapter
- Native Cline adapter
- Embeddings
- MCP server

---

## 20. Key architectural decisions

| Decision | Choice | Rationale |
|---|---|---|
| Product boundary | Collector/inbox/export layer | LLM Wiki compilers already exist; source management is the gap. |
| CASS use | External bridge | Fast local agent coverage without fork/vendor risk. |
| Source of truth | AIVault SQLite + raw refs | Need statuses, batches, dedupe, redaction, and export manifests. |
| Raw policy | Immutable | Needed for audit and reprocessing. |
| MVP UI | CLI first | Faster iteration and easier automation. |
| Search | SQLite FTS5 first | Good enough, local, simple. |
| Embeddings | P1 | Avoid early complexity. |
| Web AI ingestion | Official export/folder import first | Lower risk than private API scraping. |
| Wiki output | Deterministic Markdown | Compatible with llm-wiki, Obsidian, Git. |

---

## 21. References

- CASS GitHub repository: https://github.com/Dicklesworthstone/coding_agent_session_search
- CASS license: https://raw.githubusercontent.com/Dicklesworthstone/coding_agent_session_search/main/LICENSE
- Claude Code sessions: https://code.claude.com/docs/en/sessions
- Claude Code SDK sessions: https://code.claude.com/docs/en/agent-sdk/sessions
- Codex CLI features: https://developers.openai.com/codex/cli/features
- Codex CLI reference: https://developers.openai.com/codex/cli/reference
- ChatGPT data export: https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data
- Claude data export: https://support.claude.com/en/articles/9450526-how-can-i-export-my-claude-data
- Cline task management: https://docs.cline.bot/core-workflows/task-management
