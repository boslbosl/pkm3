# PRD — AIVault

**Version:** Canonical v0.4
**Date:** 2026-06-13
**Product name:** AIVault / AI Session Vault
**Product type:** Local-first AI session collector, inbox, search, triage, browse, and LLM Wiki export layer
**Decision:** Implement this canonical scope only. Older PRD/architecture variants are superseded.

> **v0.4 additions over v0.3:** Antigravity (IDE + CLI) as a supported source; cross-OS collection between WSL and Windows (selectable in both directions); a local web frontend for navigation, search, grouping (by project/repo and chronologically), and full metadata inspection. See §14 for the PM/developer/user review that drove these changes.

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
- Antigravity (IDE and CLI)
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

### 6.6 Collect across WSL and Windows

As a user who runs AI tools both in WSL and natively on Windows, I want to
collect sessions from the *other* OS without copying files by hand.

Acceptance criteria:

- An `--os-scope` option selects where to look: `native`, `windows`, `wsl`, or `all`.
- From inside WSL, `windows` scans Windows user profiles via `/mnt/<drive>/Users/*`.
- From Windows, `wsl` scans installed distros via `\\wsl.localhost\<distro>\home\*`
  (and the legacy `\\wsl$\...` root).
- `discover` reports each candidate with its `os_context` (`native` / `windows` / `wsl`)
  so the two sides are never silently merged.
- Cross-OS paths are preserved verbatim on the raw artifact and session records.

---

### 6.7 Browse the vault in a web UI

As a user, I want a local web frontend to navigate and search my whole history,
the way Codex or Claude Desktop let me browse conversations.

Acceptance criteria:

- `aivault serve` starts a local-only web app (default `127.0.0.1`), no cloud.
- Three views over the same data: **by project/repo**, **by source tool**, and a
  flat **chronological** timeline of everything.
- A search box runs the same FTS query as the CLI and filters the current view.
- Selecting a session shows **all** of its metadata: source tool/kind, project and
  repo path, timestamps, status, sensitivity, tags, dedupe/content hashes, raw
  artifact path, extracted commands/files, redaction findings, and the full message
  transcript.
- Read-only in v0.4; triage actions over the API are a fast follow.

---

## 7. Source support strategy

### Implemented adapters (v0.4)

All of the following ship with format-aware, version-tolerant adapters and tests:

1. Claude Code JSONL — *native, sync-discoverable*
2. Codex JSONL — *native, sync-discoverable*
3. Antigravity (IDE + CLI) local logs — *native, sync-discoverable*
4. Cline task history (`api_conversation_history.json`) — *native, sync-discoverable*
5. Cursor exported conversation (JSON/JSONL) — *import-file/import-folder*
6. SpecStory Markdown history — *import-file/import-folder*
7. ChatGPT official export (`.zip` or `conversations.json`) — *import-file*
8. Claude official export (`.zip` or `conversations.json`) — *import-file*
9. Folder import for Markdown/JSON/HTML/TXT exports — *generic fallback*

Tools with a known on-disk location are also reachable via `aivault sync <tool>`
with cross-OS discovery (WSL ↔ Windows) via `--os-scope`.

### Optional bridge

10. CASS bridge for coding-agent discovery, search, and import assistance

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
source_tool: claude-code | codex | antigravity | chatgpt | claude | perplexity | cursor | cline | specstory | cass | folder
source_kind: local-log | official-export | browser-export | markdown-folder | cass-export | manual
os_context: native | windows | wsl
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

v0.4 additions to MVP:

- Antigravity (IDE + CLI) adapter (best-effort, version-tolerant)
- Cross-OS collection between WSL and Windows (`--os-scope`)
- Local read-only web frontend: project/repo, source, and chronological views;
  shared FTS search; full per-session metadata inspection

MVP excludes:

- Cloud sync
- Team permissions
- Embeddings
- Automatic summarization by hosted LLM
- Notion write integration
- MCP server
- Write/triage actions from the web UI (read-only in v0.4)
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

---

## 14. Review and improvements (PM / Developer / User)

The v0.4 scope was reviewed from three angles. Each improvement below is either
already reflected in this PRD or tracked as a fast follow.

### 14.1 Product manager view

| Concern | Improvement |
|---|---|
| Web UI risks scope creep against the "CLI-first, local-first" promise. | Web UI ships **read-only** in v0.4. It is a *browse/search* surface over the existing DB, not a second write path. Triage stays in the CLI until the read-only UI proves stable. |
| "Done" was hard to measure for new features. | Added concrete acceptance criteria to §6.6 (cross-OS) and §6.7 (web), and explicit success metrics in §11. |
| Antigravity storage format is not yet stable/known. | Classified Antigravity as a **best-effort, version-tolerant** adapter with the generic folder importer as fallback, so an unknown format never blocks a release. |
| Cross-OS merging could silently double-count sessions across WSL/Windows. | `os_context` is now a first-class field; discovery reports it, and dedupe keys already incorporate the original path so the same file seen from two mounts is detected. |

### 14.2 Developer view

| Concern | Improvement |
|---|---|
| Adapter `discover()` hard-coded OS paths. | Introduce a `platform_paths` layer that enumerates Windows/WSL home directories; adapters compose tool sub-paths on top, and `discover(os_scope)` filters by context. Testable by injecting fake home roots. |
| Web UI as a heavy framework would add a build step and break "no daemon, easy install". | The frontend is a **dependency-free** local server (Python stdlib) serving a small static app + JSON API. No node build, no extra runtime deps. |
| API logic mixed with HTTP would be hard to test. | Web API is split into pure functions (`web/api.py`) returning plain dicts from a `Vault`, with the HTTP server as a thin transport — unit-testable without sockets. |
| "Repo" vs "project" grouping was ambiguous. | Persist the project **root path** (repo dir) alongside the display name so the UI can group by full repo path, distinguishing same-named folders. |
| Cross-OS file access can raise permission/encoding errors mid-scan. | Discovery and import tolerate unreadable/odd-encoded files (skip with a logged warning) rather than aborting a sync. |

### 14.3 User (owner) view

| Want | Improvement |
|---|---|
| "See everything, the way Codex/Claude Desktop do." | Three complementary views — by project/repo, by tool, and a global chronological timeline — over one dataset. |
| "Show me *all* the metadata, not a summary." | Session detail exposes every stored field, including hashes, raw artifact path, extracted commands/files, and redaction findings. |
| "Collect my Windows desktop tools while I live in WSL (and vice versa)." | `--os-scope {native,windows,wsl,all}` on `discover`/`sync`, working in both directions. |
| "Don't make me babysit a server." | `aivault serve` is one command, local-only by default, and stops with Ctrl-C; the vault remains a plain folder. |
