# ARCHITECTURE: AI Session Vault Collector

**Document status:** Draft v0.2  
**Date:** 2026-06-12  
**Working product name:** `aivault` / AI Session Vault  
**Scope:** Local-first AI session collector, normalized store, triage UI, and LLM Wiki exporter.

---

## 1. System Context

`aivault` sits between AI tools and downstream knowledge systems.

```text
[AI Tools]
  ChatGPT / Claude / Perplexity
  Codex CLI/Desktop / Claude Code / Cursor / Cline / SpecStory
        │
        ▼
[aivault]
  discover -> collect/import -> raw store -> normalize -> index -> triage -> export
        │
        ├── Local UI
        ├── CLI/API/MCP
        ├── LLM Wiki export
        ├── Obsidian export
        ├── Notion-ready export
        └── JSONL/context packs
```

The product is not a replacement for LLM Wiki, Obsidian, Notion, CASS, or SpecStory. It is the **collection and curation layer** that makes those systems more reliable.

---

## 2. High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                          User Interfaces                         │
│  CLI                 Local Web UI                 MCP Server      │
└──────────────┬───────────────┬────────────────────┬──────────────┘
               │               │                    │
               ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Application API                          │
│  source mgmt | sync jobs | search | triage | redaction | export   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Core Services                           │
│ Source Registry | Import Engine | Normalizer | Dedupe | Redaction │
│ Project Resolver | Capsule Generator | Export Orchestrator        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌────────────────┐    ┌────────────────┐    ┌─────────────────────┐
│ Source Adapters│    │ CASS Bridge    │    │ Export/Folder Import │
│ native scanners│    │ subprocess JSON│    │ zip/md/json/html/txt │
└────────────────┘    └────────────────┘    └─────────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Persistence Layer                        │
│ Content-addressed raw store | SQLite metadata | FTS5 | audit log  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Recommended MVP Stack

### 3.1 Backend

- **Language:** Python 3.12+
- **CLI:** Typer
- **API:** FastAPI
- **DB:** SQLite + SQLAlchemy/SQLModel
- **Search:** SQLite FTS5 for MVP
- **Jobs:** local async task queue or simple process-level job runner
- **Packaging:** `uv`, `pipx`, later PyInstaller/Tauri bundle

Rationale:

- Source adapters require filesystem, SQLite, JSONL, zip, Markdown parsing.
- Python minimizes adapter development cost.
- SQLite keeps the product local-first and easy to inspect.
- FastAPI allows local web UI and MCP/API reuse.

### 3.2 Frontend

- **Web:** React + Vite + TanStack Table
- **Distribution:** local web server at `127.0.0.1`; later Tauri wrapper if desktop packaging is needed

### 3.3 MCP

- MCP server is a separate process that reads the same SQLite DB and uses service APIs.
- MCP is read-oriented by default: search, pack, get capsule, list recent.
- Write operations require explicit config opt-in.

---

## 4. Runtime Processes

```text
aivault CLI
  - init
  - sources discover
  - sync/import
  - search
  - export

local API server
  - serves UI
  - runs sync jobs
  - handles search/triage/export requests

optional MCP server
  - exposes agent-readable tools
  - never mutates source logs

optional CASS process
  - invoked through subprocess
  - returns JSON/Markdown exports
  - not embedded as library code
```

---

## 5. Storage Layout

Default vault layout:

```text
ai-vault/
  raw/
    blobs/
      sha256/<aa>/<hash>.bin
    manifests/
      import_batch_<id>.json
  inbox/
    capsules/
    review_notes/
  exports/
    llmwiki/
    obsidian/
    notion/
    jsonl/
  .aivault/
    config.toml
    aivault.db
    aivault.db-wal
    logs/
    cache/
    quarantine/
```

Principles:

- `raw/blobs` is content-addressed and immutable.
- `normalized` data lives in SQLite, not duplicated as loose files by default.
- `exports/` contains reproducible derived artifacts.
- `quarantine/` stores parse failures and error diagnostics.

---

## 6. Data Flow

### 6.1 Automatic source sync

```text
source path
  -> source adapter detect()
  -> scan changed files
  -> copy raw artifact to raw/blobs
  -> parse to source-specific intermediate objects
  -> normalize to canonical session schema
  -> dedupe
  -> redaction scan
  -> write SQLite rows
  -> update FTS index
  -> mark session status = new
```

### 6.2 Export/import fallback

```text
user-provided zip/folder/file
  -> import batch
  -> raw artifact store
  -> parser selection
  -> canonical session schema
  -> dedupe/redaction/index
```

### 6.3 LLM Wiki export

```text
selected sessions
  -> redaction gate
  -> capsule or transcript renderer
  -> deterministic Markdown path
  -> metadata JSON
  -> export batch record
```

---

## 7. Source Adapter Interface

Each adapter implements:

```python
class SourceAdapter:
    id: str
    display_name: str
    collection_mode: CollectionMode

    def discover(self, context: RuntimeContext) -> list[SourceInstanceCandidate]: ...
    def scan(self, source: SourceInstance, cursor: SyncCursor) -> ScanResult: ...
    def parse_artifact(self, artifact: RawArtifact) -> ParseResult: ...
    def normalize(self, parsed: ParseResult) -> list[CanonicalSession]: ...
```

Adapter constraints:

- Read-only access to source files.
- No hidden network calls.
- Must record parser version.
- Must tolerate partial/corrupt files.
- Must return structured parse errors.

---

## 8. MVP Adapters

| Adapter | Input | Priority | Notes |
|---|---|---:|---|
| `claude_code` | JSONL under `~/.claude/projects` | P0 | separate Windows/WSL instances |
| `codex_cli` | local transcript files under `~/.codex/sessions` | P0 | supports current CLI sessions first |
| `chatgpt_export` | official export zip, `conversations.json` | P0 | export fallback, not scraping |
| `cass_bridge` | CASS JSON/Markdown output | P0 | optional external process |
| `specstory` | `.specstory/history/*.md` | P1 | folder import |
| `cursor` | `state.vscdb` SQLite | P1 | schema drift risk; read-only copy first |
| `cline` | VS Code global storage task directories | P1 | task-level parser |
| `claude_export` | official Claude export | P1 | export fallback |
| `perplexity_export` | Markdown/HTML/Notion export | P2 | manual/export first |

---

## 9. CASS Bridge Architecture

### 9.1 Why CASS bridge exists

CASS already handles several hard problems:

- local path discovery for many coding agents
- agent-specific format parsing
- normalization of roles, timestamps, and tool call content
- duplicate reduction
- lexical/semantic search
- JSON robot mode for automation
- Markdown/JSON/HTML export

`aivault` should use this as an accelerator without inheriting CASS as the product core.

### 9.2 Integration boundary

```text
aivault
  └── CassBridgeAdapter
        ├── checks cass executable/version
        ├── runs cass capabilities --json
        ├── runs cass sessions/search/export commands
        ├── imports CASS output into canonical schema
        └── records cass_version + command + source_path in import_batch
```

CASS is a subprocess dependency, not a library dependency.

```text
DO:
  - invoke cass via subprocess
  - parse stable JSON output
  - import exported JSON/Markdown as raw artifacts
  - show CASS bridge status in source dashboard

DO NOT:
  - copy CASS source code
  - require CASS for aivault to work
  - treat CASS index as authoritative raw source
  - mutate CASS data directory
```

### 9.3 Bridge commands

Expected bridge commands:

```bash
cass capabilities --json
cass triage --json
cass sessions --current --json
cass sessions --workspace "$PWD" --json --limit 100
cass search "auth refresh" --robot --limit 20 --fields summary
cass export /path/to/session.jsonl --format json --include-tools
cass export /path/to/session.jsonl --format markdown
```

### 9.4 Bridge import model

CASS output is represented as:

```text
SourceInstance(source_tool="cass", subtype="bridge")
ImportBatch(importer="cass_bridge", cass_version, command, started_at, completed_at)
RawArtifact(kind="cass_export_json" | "cass_export_markdown" | "cass_search_result")
CanonicalSession(source_tool=<underlying_agent>, source_bridge="cass")
```

### 9.5 Failure handling

- CASS unavailable: adapter disabled, native adapters continue.
- CASS command fails: import batch status `failed`, stderr captured.
- CASS schema changes: parser quarantines artifact and logs version.
- CASS returns references only: session remains `external_reference` until full export import.

---

## 10. Canonical Data Model

### 10.1 Core entities

```text
SourceInstance
  id
  source_tool
  display_name
  runtime_context
  root_path
  collection_mode
  status
  last_discovered_at
  last_synced_at

ImportBatch
  id
  source_instance_id
  importer
  importer_version
  started_at
  completed_at
  status
  command
  stats_json

RawArtifact
  id
  import_batch_id
  original_path
  content_hash
  byte_size
  media_type
  stored_blob_path
  parser_id
  parser_version

Session
  id
  source_tool
  source_instance_id
  bridge_tool
  source_session_id
  title
  first_user_prompt
  summary
  project_key
  workspace_path
  runtime_context
  model
  agent_version
  started_at
  ended_at
  captured_at
  message_count
  tool_call_count
  content_hash
  conversation_fingerprint
  sensitivity
  status

Message
  id
  session_id
  source_message_id
  role
  content
  content_hash
  created_at
  token_count
  ordinal

ToolCall
  id
  session_id
  message_id
  tool_name
  arguments_json
  result_preview
  status
  started_at
  ended_at

FileReference
  id
  session_id
  path
  normalized_path
  operation
  language

CommandReference
  id
  session_id
  command
  cwd
  exit_code
  started_at

RedactionFinding
  id
  session_id
  artifact_id
  finding_type
  severity
  location
  preview
  policy_version

ExportBatch
  id
  target
  exporter
  status
  started_at
  completed_at
  redaction_policy
```

---

## 11. Database Schema Sketch

```sql
CREATE TABLE source_instances (
  id TEXT PRIMARY KEY,
  source_tool TEXT NOT NULL,
  display_name TEXT,
  runtime_context TEXT NOT NULL,
  root_path TEXT,
  collection_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  last_discovered_at TEXT,
  last_synced_at TEXT
);

CREATE TABLE import_batches (
  id TEXT PRIMARY KEY,
  source_instance_id TEXT,
  importer TEXT NOT NULL,
  importer_version TEXT,
  command TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  stats_json TEXT,
  FOREIGN KEY(source_instance_id) REFERENCES source_instances(id)
);

CREATE TABLE raw_artifacts (
  id TEXT PRIMARY KEY,
  import_batch_id TEXT NOT NULL,
  original_path TEXT,
  content_hash TEXT NOT NULL,
  byte_size INTEGER,
  media_type TEXT,
  stored_blob_path TEXT NOT NULL,
  parser_id TEXT,
  parser_version TEXT,
  UNIQUE(content_hash),
  FOREIGN KEY(import_batch_id) REFERENCES import_batches(id)
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  source_tool TEXT NOT NULL,
  source_instance_id TEXT,
  bridge_tool TEXT,
  source_session_id TEXT,
  title TEXT,
  first_user_prompt TEXT,
  summary TEXT,
  project_key TEXT,
  workspace_path TEXT,
  runtime_context TEXT,
  model TEXT,
  agent_version TEXT,
  started_at TEXT,
  ended_at TEXT,
  captured_at TEXT,
  message_count INTEGER DEFAULT 0,
  tool_call_count INTEGER DEFAULT 0,
  content_hash TEXT,
  conversation_fingerprint TEXT,
  sensitivity TEXT DEFAULT 'internal',
  status TEXT DEFAULT 'new'
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  source_message_id TEXT,
  role TEXT NOT NULL,
  content TEXT,
  content_hash TEXT,
  created_at TEXT,
  ordinal INTEGER NOT NULL,
  token_count INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,
  session_id UNINDEXED,
  role UNINDEXED,
  content='messages',
  content_rowid='rowid'
);
```

---

## 12. Dedupe Strategy

### 12.1 Artifact-level dedupe

- Hash raw file bytes with SHA-256.
- Store raw blob once.
- Multiple import batches can point to same blob.

### 12.2 Message-level dedupe

- Hash normalized `(role, content, timestamp_bucket)`.
- Avoid duplicate messages from repeated syncs.

### 12.3 Session-level dedupe

- Conversation fingerprint from first N normalized message hashes.
- Secondary fingerprint from title, first prompt, start date, source tool, project.
- Duplicate groups shown in UI before merge.

### 12.4 Source priority

When the same session arrives from multiple routes:

```text
native source JSONL/SQLite > official export > CASS export > browser extension export > manual paste
```

This priority is configurable.

---

## 13. Project Resolution

A session maps to a `project_key` through ordered heuristics:

1. Explicit workspace path from source metadata.
2. Git root detected from workspace path.
3. CASS workspace field or source path.
4. User-defined path mapping.
5. Folder name from import path.
6. Manual assignment.

Windows/WSL mapping example:

```toml
[path_mappings]
"C:\\Users\\me\\dev\\myrepo" = "/home/me/dev/myrepo"
"\\\\wsl.localhost\\Ubuntu\\home\\me\\dev\\myrepo" = "/home/me/dev/myrepo"
```

---

## 14. Redaction Architecture

```text
normalized session
  -> redaction scanner
  -> findings table
  -> export gate
  -> redacted renderer
```

Rules:

- Raw artifacts are never edited.
- Redaction is applied at render/export time.
- Findings are linked to session/artifact/message offsets.
- Strict mode blocks export on high severity findings.

Initial detectors:

- OpenAI/Anthropic/GitHub-style API keys
- generic bearer tokens
- JWT-like values
- private key blocks
- `.env` key/value patterns
- AWS-like credentials
- high-entropy strings
- email addresses
- local absolute paths

---

## 15. Search Architecture

MVP:

```text
SQLite sessions/messages
  -> FTS5 messages_fts
  -> query parser
  -> filters/aggregations
  -> ranked session/message results
```

Future:

```text
local embeddings
  -> vector table or LanceDB/SQLite-vss
  -> hybrid lexical + vector ranking
```

Search API examples:

```http
GET /api/search?q=refresh%20token&project=myrepo&source=claude_code&limit=20
GET /api/sessions?status=wiki_ready&source=codex
GET /api/projects/myrepo/timeline
```

CLI examples:

```bash
aivault search "refresh token" --project myrepo --json
aivault sessions --source claude-code --status new
aivault timeline --project myrepo --days 14
```

---

## 16. Export Architecture

### 16.1 LLM Wiki exporter

Target layout:

```text
llm-wiki/
  raw/
    sessions/
      <project>/
        2026-06-12_claude-code_auth-refresh_<session-id>.md
  inbox/
    capsules/
      <project>/
        2026-06-12_claude-code_auth-refresh_<session-id>.md
```

Session Markdown frontmatter:

```yaml
---
source_tool: claude-code
source_instance: claude-code-wsl
bridge_tool: null
project: myrepo
workspace_path: /home/me/dev/myrepo
runtime_context: wsl
started_at: 2026-06-12T21:30:00+09:00
captured_at: 2026-06-12T22:10:00+09:00
model: claude-sonnet-4
status: wiki-ready
raw_artifact_hash: sha256:...
conversation_fingerprint: blake3:...
sensitivity: internal
---
```

### 16.2 Export modes

| Mode | Output | Best for |
|---|---|---|
| `transcript` | full normalized Markdown transcript | audit/detail |
| `capsule` | compact summary | LLM Wiki ingest |
| `bundle` | transcript + capsule + metadata JSON | archival |
| `context-pack` | token-budgeted Markdown | feeding current agent |

### 16.3 Export guarantees

- Deterministic filenames.
- Export batch records selected session ids and renderer version.
- Redaction policy included in metadata.
- Existing user-edited files are not overwritten without confirmation.

---

## 17. Local Web UI Architecture

Pages:

```text
/dashboard
/sources
/imports
/inbox
/sessions/:id
/projects/:projectKey
/duplicates
/redaction
/exports
/settings
```

State management:

- Server is source of truth.
- UI uses query params for filters.
- Bulk actions are submitted as explicit jobs.
- Long-running sync/export jobs are polled or streamed via SSE.

---

## 18. MCP Server Architecture

MCP tools:

```text
search_sessions(query, project?, source?, days?, limit?)
get_session(session_id, include_messages?, redacted?)
get_capsule(session_id)
pack_context(session_ids[], max_tokens, redacted=true)
list_recent(project?, days?)
list_wiki_ready(project?)
```

Default permissions:

- Read-only.
- Redacted outputs by default.
- Mutation tools disabled unless explicitly configured.

---

## 19. Security and Privacy

### 19.1 Defaults

- No cloud sync.
- No telemetry.
- No source mutation.
- No browser cookie scraping.
- No decryption bypass.
- Redaction warnings before export.

### 19.2 Threats

| Threat | Mitigation |
|---|---|
| leaking API keys through export | redaction scanner, strict mode |
| prompt injection from old sessions | treat raw as untrusted source; context packs include source labels |
| accidental sharing of raw logs | export review gates |
| corrupted source DB | read-only copy before parsing SQLite |
| schema drift | parser versioning and quarantine |
| bridge command injection | strict argument arrays, no shell interpolation |

---

## 20. Job System

Jobs:

```text
source_discovery
source_sync
import_batch
parse_artifacts
redaction_scan
fts_rebuild
capsule_generate
export_batch
cass_bridge_import
```

Job states:

```text
queued -> running -> succeeded
queued -> running -> failed
queued -> cancelled
```

Every job records:

- job id
- type
- args hash
- started/completed timestamps
- log path
- created/updated row counts
- failure reason

---

## 21. Error and Quarantine Model

Parse errors do not stop the entire sync.

```text
RawArtifact
  -> parse failed
  -> QuarantineRecord
  -> source health warning
  -> UI action: retry / ignore / open raw / report fixture
```

Quarantine record fields:

- artifact id
- adapter id
- parser version
- exception class
- error message
- source path
- sample preview, redacted

---

## 22. Testing Strategy

### 22.1 Unit tests

- parser fixtures for each source
- redaction detectors
- dedupe hashing
- path mapping
- Markdown rendering

### 22.2 Integration tests

- sync idempotency
- import/export roundtrip
- CASS bridge with mocked JSON outputs
- Windows/WSL path mapping
- corrupted SQLite/JSONL handling

### 22.3 Golden files

- canonical session JSON for known fixtures
- LLM Wiki Markdown output
- capsule output
- redaction preview output

---

## 23. Migration and Versioning

- SQLite migrations with Alembic or lightweight migration table.
- Adapter parser versions stored per artifact/session.
- Export renderer version stored per export batch.
- Config schema version stored in `.aivault/config.toml`.

---

## 24. Development Phases

### Phase 0: Spike

- Validate source paths.
- Implement canonical schema.
- Test CASS bridge outputs.
- Build Claude Code and Codex parser spikes.

### Phase 1: CLI MVP

Commands:

```bash
aivault init
aivault sources discover
aivault sync
aivault sync --from cass
aivault import <zip-or-folder>
aivault search <query>
aivault export llmwiki
```

### Phase 2: Local Web UI

- Dashboard
- Source health
- Inbox
- Session detail
- Export queue

### Phase 3: Native coverage

- Cursor native parser
- Cline native parser
- Claude export parser
- Perplexity export parser

### Phase 4: Agent integration

- MCP server
- context pack builder
- capsule generation
- project-aware search

### Phase 5: Optional team mode

- encrypted shared vault
- reviewed-only publication
- role-based access
- audit reports

---

## 25. Reference Notes

- CASS GitHub: https://github.com/Dicklesworthstone/coding_agent_session_search
- Claude Code sessions: https://code.claude.com/docs/en/sessions
- OpenAI Codex CLI features: https://developers.openai.com/codex/cli/features
- Cline task history: https://docs.cline.bot/core-workflows/task-management
- Cursor local chat history discussion: https://forum.cursor.com/t/chat-history-folder/7653
