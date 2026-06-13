# PRD — AIVault

**Version:** Canonical v0.3  
**Date:** 2026-06-12  
**Product name:** AIVault / AI Session Vault  
**Product type:** Local-first AI session collector, inbox, search, triage, and LLM Wiki export layer  
**Decision:** Implement this canonical scope only. Older PRD/architecture variants are superseded.

---

## 1. Summary

AIVault collects and imports AI conversations, coding-agent sessions, and generated outputs from multiple tools into a local vault. It normalizes them into a canonical session model, indexes them for search, supports human triage and redaction, and exports selected sessions into LLM Wiki-compatible Markdown or other knowledge destinations.

AIVault is not itself the final LLM Wiki. It is the **source collection and curation layer** before the LLM Wiki.

---

## 2. Problem

AI-heavy developers and vibe-coding users generate valuable work knowledge across many tools:

- ChatGPT
- Claude / Claude Desktop
- Perplexity
- Codex CLI/Desktop/WSL
- Claude Code on Windows and WSL
- Cursor
- Cline
- SpecStory
- Browser extension exports
- Official export zips
- Notion-based exports

This creates several problems:

1. Sessions are scattered across different applications and filesystems.
2. Each tool uses different storage formats: JSONL, SQLite, Markdown, HTML, JSON, ZIP, Notion export, or local app storage.
3. Important reasoning, commands, failed attempts, file edits, and decisions are difficult to retrieve later.
4. Raw transcripts are too noisy to put directly into an LLM Wiki.
5. Manual export is incomplete, but fully automatic collection produces too much unreviewed material.
6. Raw evidence and generated wiki summaries must remain separate.

---

## 3. Target users

### Primary user

A developer using multiple AI coding assistants and web AI tools who wants to reuse prior work context.

### Secondary users

- Small AI-heavy engineering teams
- Vibe-coding practitioners
- Researchers who use several LLM tools
- Power users maintaining Obsidian, Notion, or LLM Wiki knowledge bases

---

## 4. Product goals

AIVault must:

1. Discover and import AI sessions from local and export-based sources.
2. Preserve original raw evidence immutably.
3. Normalize sessions into a common schema.
4. Provide fast local search.
5. Let users review, tag, ignore, keep, or mark sessions as wiki-ready.
6. Provide redaction preview before export.
7. Export selected sessions to downstream knowledge systems.
8. Avoid lock-in by keeping filesystem-readable artifacts.

---

## 5. Non-goals

AIVault does not aim to:

- Replace ChatGPT, Claude, Cursor, Cline, Codex, or Claude Code.
- Replace Pratiyush/llm-wiki or another LLM Wiki compiler.
- Automatically trust LLM-generated summaries as source of truth.
- Upload private sessions to a cloud service by default.
- Implement all adapters in the first MVP.
- Depend on CASS as its internal database or source of truth.

---

## 6. Core user stories

### 6.1 Discover local sessions

As a user, I want AIVault to find local Claude Code and Codex sessions so I can see what work history exists.

Acceptance criteria:

- `aivault discover` lists supported sources.
- Results include source type, path, OS context, and estimated session count.
- Windows and WSL paths are represented separately.

---

### 6.2 Import sessions

As a user, I want to import sessions into a local vault without losing the raw original file.

Acceptance criteria:

- Original file or export is copied into `raw/`.
- A normalized session row is created.
- Messages are extracted when possible.
- Import is idempotent.

---

### 6.3 Search prior work

As a user, I want to search all imported sessions regardless of which AI tool produced them.

Acceptance criteria:

- Search works across session title, prompt, response, file paths, commands, and extracted snippets.
- Results show source, project, date, and summary.
- User can open the raw source or normalized session.

---

### 6.4 Triage sessions

As a user, I want to separate important sessions from noise before exporting them to a wiki.

Acceptance criteria:

- Supported statuses: `new`, `reviewed`, `keep`, `ignore`, `wiki_ready`, `exported`.
- User can add tags and notes.
- User can filter by status, source, project, and date.

---

### 6.5 Export to LLM Wiki

As a user, I want selected sessions exported in a format that downstream LLM Wiki tools can ingest.

Acceptance criteria:

- Export only selected statuses, typically `wiki_ready`.
- Export includes Markdown frontmatter.
- Export includes links or paths to raw evidence.
- Export creates an export manifest.
- Re-running export avoids duplicate output.

---

## 7. Source support strategy

### MVP native adapters

1. Claude Code JSONL
2. Codex JSONL
3. Folder import for Markdown/JSON/HTML/TXT exports

### Near-term adapters

4. ChatGPT official export ZIP
5. Claude official export
6. SpecStory Markdown history
7. Cline task history
8. Cursor local/export adapter

### Optional bridge

9. CASS bridge for coding-agent discovery, search, and import assistance

### Later adapters

10. Perplexity export workflows
11. Notion/Pactify export folder
12. Browser extension export folders
13. MCP-accessible source folders

---

## 8. CASS relationship

CASS is relevant because it already explores the hard problem of finding local coding-agent histories across many tools. However, it should be treated as an optional external bridge.

AIVault should not fork CASS as its core product.

AIVault should use CASS in three optional ways:

1. **Discovery bridge:** identify local agent histories.
2. **Search bridge:** query existing CASS index when available.
3. **Backfill bridge:** import CASS-exported Markdown/JSON as raw artifacts.

AIVault's own raw store and canonical database remain the source of truth.

---

## 9. Data model overview

Core entities:

- `Source`
- `ImportBatch`
- `RawArtifact`
- `Session`
- `Message`
- `Snippet`
- `Attachment`
- `Project`
- `Tag`
- `TriageStatus`
- `ExportRun`
- `ExportItem`

Canonical session fields:

```yaml
session_id: string
source_tool: claude-code | codex | chatgpt | claude | perplexity | cursor | cline | specstory | cass | folder
source_kind: local-log | official-export | browser-export | markdown-folder | cass-export | manual
project_id: string | null
title: string | null
started_at: datetime | null
ended_at: datetime | null
imported_at: datetime
status: new | reviewed | keep | ignore | wiki_ready | exported
raw_artifact_id: string
dedupe_key: string
sensitivity: unknown | public | internal | confidential | secret
summary: string | null
```

---

## 10. MVP scope

MVP includes:

- CLI application
- Local vault initialization
- SQLite + FTS5 index
- Raw artifact store
- Claude Code JSONL importer
- Codex JSONL importer
- Generic folder importer
- Session listing and search
- Triage status management
- LLM Wiki Markdown export
- Basic redaction detection
- Dedupe by source fingerprint and content hash

MVP excludes:

- Full web UI
- Cloud sync
- Team permissions
- Embeddings
- Automatic summarization by hosted LLM
- Notion write integration
- MCP server
- All possible adapters

---

## 11. Success metrics

MVP success:

- Imports 100+ local sessions without duplicates.
- Search returns relevant results under 500 ms on a normal laptop-sized vault.
- User can mark sessions as wiki-ready and export them.
- Exported Markdown is usable by an LLM Wiki or Obsidian workflow.
- Raw evidence is preserved and traceable from every exported note.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Agent storage formats change | adapter versioning, source health checks, tests with fixtures |
| Sensitive data leakage | local-first default, redaction preview, export allowlist |
| Duplicate imports | content hashing and source fingerprints |
| Cursor/Cline schema drift | treat as best-effort adapters; keep generic folder import fallback |
| CASS license or packaging risk | optional subprocess bridge, no source-code copy in MVP |
| Wiki export noise | triage statuses and capsule generation before export |

---

## 13. First implementation milestone

The first milestone is a vertical slice:

```text
Claude Code JSONL fixture
  -> import into raw store
  -> normalize into Session/Message
  -> search with FTS5
  -> mark wiki_ready
  -> export LLM Wiki Markdown
```

This milestone must work before building UI, Notion, MCP, embeddings, or broad adapter coverage.
