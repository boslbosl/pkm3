# PRD: AI Session Vault Collector

**Document status:** Draft v0.2  
**Date:** 2026-06-12  
**Working product name:** `aivault` / AI Session Vault  
**Primary audience:** 개인 개발자, vibe-coding 사용자, AI-heavy 개발팀  
**Primary job-to-be-done:** ChatGPT, Codex, Perplexity, Claude, Cursor, Cline 등 여러 AI 도구에 흩어진 대화와 coding-agent 세션을 로컬에서 수집, 정규화, 검색, triage하고 LLM Wiki/Obsidian/Notion/MCP로 재사용한다.

---

## 1. Executive Summary

`aivault`는 여러 AI 도구의 conversation/session/output을 한곳에 모으는 **local-first AI session collector + inbox + exporter**이다.

핵심 방향은 다음과 같다.

```text
Automatic collection where possible
Export/import where automatic collection is unavailable or unstable
Immutable raw archive
Canonical normalized sessions
Search + triage + redaction
LLM Wiki compatible export
MCP/CLI access for future agents
```

`aivault`는 LLM Wiki compiler가 아니다. LLM Wiki 앞단에서 source를 수집하고, 중복을 제거하고, 민감정보를 점검하고, 어떤 세션을 wiki에 넣을지 결정하는 **source-of-truth layer**이다.

---

## 2. Why This Product Exists

AI 작업 기록은 점점 코드 저장소가 아니라 다음 위치에 쌓인다.

- ChatGPT, Claude, Perplexity 같은 web/desktop AI 대화
- Codex CLI/Desktop, Claude Code, Cursor, Cline 같은 coding-agent 세션
- Windows native, WSL, macOS, Linux의 서로 다른 home directory
- JSONL, SQLite, Markdown, HTML, official export zip, Notion export 등 서로 다른 저장 형식
- agent가 수행한 command, file edit, tool call, error analysis, decision, plan

현재 문제는 다음과 같다.

1. **도구별 저장소가 분산되어 있다.** 같은 프로젝트의 지식이 ChatGPT, Claude Code, Cursor, Codex에 흩어진다.
2. **세션 단위 구조화가 약하다.** “무슨 문제를 어떤 agent가 어떻게 해결했는지”가 한눈에 보이지 않는다.
3. **검색은 가능해도 선별이 어렵다.** 모든 raw transcript를 LLM Wiki에 넣으면 노이즈와 비용이 커진다.
4. **자동 수집과 수동 export가 동시에 필요하다.** 일부 도구는 로컬 로그를 읽을 수 있지만, 일부는 official export나 browser extension export가 현실적이다.
5. **raw와 generated wiki를 분리해야 한다.** LLM-generated wiki는 유용하지만 원문 증거가 아니다.

---

## 3. CASS와의 관계

CASS, 즉 `coding_agent_session_search`, 는 `aivault` 요구와 상당히 겹치는 기존 프로젝트다. CASS는 Codex, Claude Code, Gemini CLI, Cline, Cursor, ChatGPT, Aider 등 여러 local coding-agent history를 검색 가능한 timeline으로 모으고, agent별 JSONL/SQLite/Markdown/JSON 포맷을 `Conversation -> Message -> Snippet` 모델로 정규화한다.

그러나 `aivault`의 제품 경계는 CASS와 다르다.

| 항목 | CASS | aivault |
|---|---|---|
| 1차 목적 | local coding-agent history 검색 | collection + inbox + triage + LLM Wiki export |
| UI 중심 | TUI/CLI | local web UI + CLI + MCP |
| 데이터 상태 관리 | index/search 중심 | raw/import batch/review/export lifecycle 중심 |
| LLM Wiki export | 부가 workflow로 가능 | 1급 product output |
| web/export sources | 제한적 | official export, folder import, Notion/export fallback을 1급 처리 |
| redaction/review | 검색 노이즈 필터에 가까움 | export 전 redaction/review workflow |

### Product decision

CASS는 **fork 대상이 아니라 optional bridge/adapter 대상**으로 사용한다.

```text
MVP:
  - cass가 설치되어 있으면 cass --json / --robot 출력과 export 결과를 import한다.
  - cass의 connector coverage를 빠르게 활용한다.
  - cass 코드는 복사하지 않는다.

Long term:
  - aivault native adapters를 점진적으로 늘린다.
  - cass bridge는 power-user compatibility path로 유지한다.
```

이유:

- CASS는 connector coverage가 좋다.
- 하지만 제품 UX와 data lifecycle은 `aivault`와 다르다.
- CASS license는 MIT에 OpenAI/Anthropic rider가 붙어 있으므로, 코드를 직접 fork/copy하기 전에 법무 검토가 필요하다.
- 외부 process bridge로 사용하면 빠른 실험과 독립적인 제품 구조를 동시에 얻을 수 있다.

---

## 4. Product Vision

사용자는 `aivault`를 통해 다음을 달성한다.

```text
1. 여러 AI 도구의 세션을 자동 또는 export 기반으로 수집한다.
2. 수집된 세션을 agent, project, date, model, file, command, topic 기준으로 탐색한다.
3. 중요한 세션을 keep / ignore / summarize / wiki-ready / exported 상태로 관리한다.
4. raw transcript와 generated capsule/wiki를 분리한다.
5. 선택된 세션을 LLM Wiki raw source, Obsidian note, Notion-ready Markdown, JSONL, MCP context pack으로 내보낸다.
6. 새로운 Claude Code/Codex/Cursor/Cline 세션이 과거 세션을 검색해 재사용할 수 있게 한다.
```

---

## 5. Product Principles

1. **Local-first**  
   기본 동작에서는 원문 대화와 세션을 외부 서버로 보내지 않는다.

2. **Read-only source ingestion**  
   source adapter는 원본 agent 로그를 수정하거나 삭제하지 않는다.

3. **Raw is immutable**  
   원문 raw는 hash/provenance와 함께 저장하고 수정하지 않는다.

4. **Derived data is rebuildable**  
   index, embeddings, generated capsules, exports, wiki pages는 raw/normalized data에서 재생성 가능해야 한다.

5. **Triage before wiki**  
   모든 세션을 바로 LLM Wiki에 넣지 않는다. `new -> reviewed -> wiki-ready -> exported` workflow를 둔다.

6. **Export fallback is first-class**  
   자동 수집이 불가능하거나 취약한 source는 official export, Markdown export, Notion export, manual folder import로 받는다.

7. **Windows/WSL first-class**  
   Windows native와 WSL은 별도 runtime/source instance로 취급한다.

8. **No hidden mutation**  
   사용자가 선택하기 전에는 raw deletion, source compaction, remote upload, wiki overwrite를 하지 않는다.

---

## 6. Target Users

### 6.1 Persona A: Solo Vibe Coder

- ChatGPT, Codex CLI, Claude Code, Cursor, Cline을 병행 사용한다.
- “지난번에 Cursor가 해결한 오류를 Claude Code에서 다시 찾고 싶다.”
- 로컬 기록을 잃지 않고, 프로젝트별로 LLM Wiki화하고 싶다.

### 6.2 Persona B: AI-heavy 개발팀 리드

- 팀원마다 다른 AI 도구를 쓴다.
- 반복되는 debugging, migration, architecture decision을 팀 지식으로 남기고 싶다.
- raw log는 민감하므로 review/redaction 후 공유하고 싶다.

### 6.3 Persona C: Research/PM/Builder

- ChatGPT/Claude/Perplexity 리서치 대화가 많다.
- Notion/Obsidian/LLM Wiki로 장기 지식을 쌓고 싶다.
- browser extension 또는 official export 기반 import가 필요하다.

---

## 7. Source Coverage

### 7.1 MVP source types

| Source | Collection mode | MVP priority | Notes |
|---|---:|---:|---|
| Claude Code Windows | automatic local scan | P0 | `~/.claude/projects` equivalent under Windows home |
| Claude Code WSL | automatic local scan | P0 | WSL home의 `~/.claude/projects` 별도 source instance |
| Codex CLI Windows | automatic local scan | P0 | `~/.codex/sessions` equivalent under Windows home |
| Codex CLI WSL | automatic local scan | P0 | WSL home의 `~/.codex/sessions` 별도 source instance |
| Cursor | automatic local scan | P0/P1 | SQLite `state.vscdb`; schema drift risk 높음 |
| Cline | automatic local scan | P0/P1 | VS Code global storage task directories |
| CASS bridge | external process import | P0 | 빠른 coverage 확보용 optional bridge |
| SpecStory | folder import | P1 | `.specstory/history/*.md` Markdown source |
| ChatGPT official export | zip import | P0 | `conversations.json` parser |
| Claude official export | zip/folder import | P0 | export parser |
| Perplexity | manual/export import | P1 | Markdown/HTML/Notion export fallback 우선 |
| AI Toolbox / AI Exporter output | folder import | P1 | Markdown/JSON/PDF/TXT source import |
| Pactify/Notion export | folder/API import | P2 | Notion-first workflow 사용자를 위한 option |

### 7.2 Non-MVP source types

- Grok, Gemini web, DeepSeek, GitHub Copilot Chat, Aider, OpenCode, Amp, Factory/Droid
- Team/shared cloud sync
- Direct browser automation scraping
- Automated login/session-cookie based extraction

---

## 8. Functional Requirements

### 8.1 Vault initialization

**Command:**

```bash
aivault init ~/ai-vault
```

**Creates:**

```text
ai-vault/
  raw/
  inbox/
  normalized/
  exports/
  wiki_out/
  .aivault/
    config.toml
    aivault.db
    logs/
```

Acceptance criteria:

- Can create a vault in an arbitrary folder.
- Existing vault is detected and not overwritten.
- Config records OS, timezone, and default redaction policy.

---

### 8.2 Source discovery

**Command:**

```bash
aivault sources discover
```

Capabilities:

- Detect known local paths for Claude Code, Codex, Cursor, Cline, SpecStory.
- Detect Windows and WSL path pairs.
- Detect CASS installation and capabilities when available.
- Classify source as `automatic`, `watchable`, `export-only`, or `manual`.

Acceptance criteria:

- Shows source name, path, status, estimated session count, last modified time.
- Does not parse full content during discovery unless user asks.
- Does not modify source files.

---

### 8.3 Source sync

**Commands:**

```bash
aivault sync
aivault sync --source claude-code-wsl
aivault sync --from cass
```

Capabilities:

- Incrementally import changed/new sessions.
- Create import batches.
- Preserve raw source hash and parser version.
- Skip unchanged sessions.
- Quarantine parse failures.

Acceptance criteria:

- Sync is idempotent.
- Re-running sync does not create duplicate canonical sessions.
- Parse failures are visible in UI and CLI.

---

### 8.4 Export/import fallback

**Commands:**

```bash
aivault import chatgpt-export.zip --source chatgpt
aivault import claude-export.zip --source claude
aivault import ./perplexity-exports --source perplexity
aivault import .specstory/history --source specstory
```

Capabilities:

- Accept zip, folder, Markdown, JSON, JSONL, HTML, TXT.
- Create import batch with file list, hashes, source mapping.
- Allow user to reclassify source if auto-detection is wrong.

Acceptance criteria:

- Import never mutates user-provided files.
- Imported artifacts are copied into content-addressed raw store.
- Duplicate import files are detected.

---

### 8.5 Canonical session normalization

Every imported session must map to a canonical model:

```text
SourceInstance
ImportBatch
RawArtifact
Session
Message
ToolCall
FileReference
CommandReference
Decision
Topic
ExportBatch
```

Minimum normalized fields:

- `session_id`
- `source_tool`
- `source_instance`
- `project_key`
- `workspace_path`
- `runtime_context`: `windows | wsl | macos | linux | web | export`
- `started_at`, `ended_at`, `captured_at`
- `model`, `agent_version` when available
- `title`, `summary`, `first_user_prompt`
- `messages[]`
- `raw_artifact_ids[]`
- `content_hash`, `conversation_fingerprint`
- `status`: `new | reviewed | ignored | summarize | wiki_ready | exported | quarantined`

---

### 8.6 Search and browsing

Required views:

- Global session list
- Source health dashboard
- Import batch history
- Project view
- Agent/source view
- Timeline/calendar view
- Duplicate groups
- Quarantine/errors
- Wiki-ready queue

Required filters:

- source tool
- project
- runtime context
- date range
- model
- status
- file path
- command
- has errors
- has code edits
- has tool calls
- sensitivity label

Search capabilities:

- SQLite FTS5 lexical search in MVP
- optional local embeddings later
- exact path/file search
- phrase search
- agent/project/date aggregation

---

### 8.7 Triage workflow

Statuses:

```text
new -> reviewed -> wiki_ready -> exported
new -> ignored
new -> summarize -> reviewed
new -> quarantined
```

User actions:

- Mark as `keep`
- Mark as `ignore`
- Mark as `wiki-ready`
- Generate capsule
- Redact selected content
- Merge duplicates
- Assign project/topic
- Link to existing wiki page
- Export selected sessions

Acceptance criteria:

- Bulk actions work on filtered session sets.
- Status changes are recorded in an audit log.
- User can undo status changes.

---

### 8.8 Redaction and safety

MVP redaction checks:

- API keys and common secret patterns
- JWT-like tokens
- SSH/private key blocks
- `.env` style values
- high-entropy strings
- email addresses and obvious PII
- local absolute paths, optionally

Modes:

```text
strict: block export until reviewed
warn: allow export with warnings
off: no redaction, local-only users
```

Acceptance criteria:

- Redaction preview shows before/after.
- Raw artifacts are never destructively edited.
- Redacted export records policy version.

---

### 8.9 Capsule generation

A capsule is a compact, wiki-ready summary of a session.

Required sections:

```markdown
# Session Capsule

## Goal
## Outcome
## Key decisions
## Files inspected or changed
## Commands run
## Errors and fixes
## Reusable knowledge
## Open questions
## Source evidence
```

MVP approach:

- Template-based extraction first.
- Optional LLM-assisted capsule generation later.
- All generated capsules are derived artifacts, not source of truth.

---

### 8.10 LLM Wiki export

**Command:**

```bash
aivault export llmwiki --status wiki-ready --target ~/llm-wiki/raw/sessions
```

Output modes:

1. `raw-session` mode: normalized transcript as Markdown with frontmatter.
2. `capsule` mode: compact session capsule.
3. `bundle` mode: raw + capsule + metadata JSON.

Acceptance criteria:

- Export is deterministic.
- Export includes source provenance and raw hash.
- Export never overwrites user-edited target files without diff/confirmation.
- Export batch can be reproduced.

---

### 8.11 MCP/agent access

Expose a local MCP server or JSON CLI for current agents.

Use cases:

```text
- Search previous sessions for similar errors.
- Fetch a cited context pack for current project.
- List wiki-ready sessions not yet exported.
- Retrieve a capsule by session id.
```

MVP CLI commands:

```bash
aivault search "auth token refresh" --project myrepo --json
aivault pack --session <id> --max-tokens 8000 --json
aivault recent --project myrepo --days 7 --json
```

---

## 9. CASS Bridge Requirements

### 9.1 CASS bridge scope

The CASS bridge is an optional integration that imports CASS-discovered sessions and search/export output into `aivault`.

MVP commands to support through subprocess invocation:

```bash
cass capabilities --json
cass triage --json
cass sessions --current --json
cass sessions --workspace <path> --json --limit <n>
cass search <query> --robot --limit <n> --fields summary
cass export <session_path> --format json --include-tools
cass export <session_path> --format markdown
```

### 9.2 CASS bridge modes

| Mode | Description | Use case |
|---|---|---|
| `discover-only` | Use CASS to identify source paths and supported agents | setup wizard |
| `search-bridge` | Use CASS search results but store only references | quick search before full import |
| `import-exported` | Use `cass export` to import sessions into aivault | MVP import |
| `index-sidecar` | Keep CASS index separate; link to CASS path | power-user mode |

### 9.3 Constraints

- Do not copy CASS code into `aivault` without legal review.
- CASS is optional; `aivault` must work without it.
- If CASS output schema changes, bridge parser should fail safely.
- Store CASS version and command used for each import batch.

---

## 10. Non-Goals

MVP does not attempt to:

- Bypass encryption in ChatGPT/Claude desktop apps.
- Scrape browser sessions using cookies.
- Become a full LLM Wiki compiler.
- Replace Obsidian/Notion as a knowledge editor.
- Replace CASS TUI as a high-performance terminal search tool.
- Sync private AI history to cloud by default.
- Automatically publish team knowledge without review.
- Train models on user data.

---

## 11. MVP User Stories

### Story 1: Discover local agent sessions

As a user, I can run `aivault sources discover` and see Claude Code, Codex, Cursor, Cline, SpecStory, and CASS availability.

Acceptance:

- Shows found sources and missing sources.
- Shows Windows and WSL instances separately.
- Does not import content yet.

### Story 2: Import Claude Code and Codex sessions

As a user, I can run `aivault sync` and see normalized sessions from Claude Code and Codex.

Acceptance:

- Sessions appear with project, source, date, title/first prompt.
- Raw artifact hash and source path are stored.
- Duplicate sync is idempotent.

### Story 3: Import ChatGPT export

As a user, I can import OpenAI export zip and search old ChatGPT conversations.

Acceptance:

- Each conversation becomes a canonical session.
- Date, title, messages, and source metadata are preserved.
- Large exports are processed incrementally.

### Story 4: Use CASS bridge

As a user with CASS installed, I can use CASS as a discovery/search/import helper.

Acceptance:

- `aivault sources discover` reports CASS installed/version.
- `aivault sync --from cass` imports CASS exported sessions.
- Import records CASS command, version, and source path.

### Story 5: Triage sessions

As a user, I can review sessions in a local UI and mark important sessions as `wiki-ready`.

Acceptance:

- Bulk select and status update work.
- Filters persist across page reload.
- Status changes are audit logged.

### Story 6: Export to LLM Wiki

As a user, I can export `wiki-ready` sessions to an LLM Wiki-compatible folder.

Acceptance:

- Exported Markdown includes frontmatter, summary, messages or capsule, and source evidence.
- Export can be repeated without creating duplicates.
- Redaction warnings appear before export.

---

## 12. UX Requirements

### 12.1 Local web UI pages

1. **Dashboard**
   - Total sessions
   - Sources healthy/stale/error
   - New sessions needing review
   - Wiki-ready count
   - Last export batch

2. **Sources**
   - Source instances
   - Paths
   - Last sync
   - Error count
   - Discovery status
   - CASS bridge status

3. **Inbox**
   - New/reviewed sessions
   - Quick filters
   - Bulk status actions
   - Redaction warnings

4. **Session detail**
   - Conversation messages
   - Tool calls
   - Files/commands/errors
   - Raw source evidence
   - Capsule preview

5. **Projects**
   - Project timeline
   - Related sessions
   - Files touched
   - decisions/open questions

6. **Exports**
   - Export batches
   - Target folder
   - Status
   - Redaction policy
   - Diff preview

---

## 13. Data Model Requirements

Minimum tables:

```text
source_instances
import_batches
raw_artifacts
sessions
messages
tool_calls
file_refs
command_refs
topics
session_topics
decisions
redaction_findings
exports
export_items
audit_log
```

Minimum indexes:

```text
sessions(source_tool, project_key, started_at)
sessions(status, started_at)
messages(session_id, role, created_at)
messages_fts(content)
raw_artifacts(content_hash)
redaction_findings(session_id, severity)
```

---

## 14. Metrics

### MVP success metrics

- Import 1,000+ sessions without duplicate explosion.
- Search response under 500ms for 100k messages on a typical laptop using FTS5.
- 95%+ idempotent sync accuracy on repeated syncs.
- User can move from raw import to LLM Wiki export in under 10 minutes for a known project.
- Zero source-file mutation by adapters.

### Product metrics

- Sessions reviewed per week
- Wiki-ready conversion rate
- Duplicate detection precision
- Redaction warning rate
- Search-to-export conversion
- Agent context pack usage

---

## 15. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agent storage schemas change | imports break | adapter versioning, parse quarantine, CASS bridge fallback |
| Cursor/Cline local DB formats drift | wrong parsing | read-only mode, schema probes, source-specific test fixtures |
| ChatGPT/Claude desktop encryption | cannot auto-ingest | official export/import fallback |
| Duplicates from multiple sources | noisy vault | content hash, conversation fingerprint, import batch provenance |
| Sensitive data export | security risk | redaction preview, strict mode, source labels |
| CASS license complexity | legal risk | subprocess bridge only; no code copy without review |
| Large logs | performance issue | incremental sync, pagination, FTS, chunked raw artifacts |
| LLM-generated summaries hallucinate | trust issue | raw evidence links, generated/derived labeling, review workflow |

---

## 16. Roadmap

### Phase 0: Spike

- Validate Claude Code parser.
- Validate Codex parser.
- Validate CASS bridge output.
- Validate ChatGPT export parser.
- Define canonical schema.

### Phase 1: MVP CLI + local DB

- `init`, `sources discover`, `sync`, `import`, `search`, `export llmwiki`
- SQLite + FTS5
- raw content-addressed store
- Claude Code, Codex, ChatGPT export, CASS bridge

### Phase 2: Local web UI

- Dashboard
- Inbox
- Session detail
- Project view
- Source health
- Export queue

### Phase 3: Broader adapters

- Cursor native parser
- Cline native parser
- Claude export parser
- Perplexity Markdown/Notion import
- SpecStory import

### Phase 4: Intelligence layer

- Capsule generation
- Topic clustering
- Similar session detection
- Local embeddings
- MCP server
- context pack generation

### Phase 5: Team mode, optional

- shared vault
- role-based access
- reviewed-only publication
- encrypted sync
- audit/reporting

---

## 17. Open Questions

1. Should `aivault` be CLI-first with web UI later, or local web UI from day one?
2. Should native adapters or CASS bridge be the MVP default?
3. Should LLM-assisted capsule generation run locally only by default?
4. What is the minimum acceptable redaction policy before export?
5. Should Notion be upstream import only, downstream export only, or both?
6. How should project identity handle moved/renamed folders across Windows and WSL?
7. Should `raw/` live inside the user vault as copied artifacts, or only store content hashes and original source pointers?

---

## 18. Reference Notes

- CASS GitHub: https://github.com/Dicklesworthstone/coding_agent_session_search
- Claude Code sessions: https://code.claude.com/docs/en/sessions
- OpenAI Codex CLI features: https://developers.openai.com/codex/cli/features
- Cline task history: https://docs.cline.bot/core-workflows/task-management
- Cursor local chat history discussion: https://forum.cursor.com/t/chat-history-folder/7653
