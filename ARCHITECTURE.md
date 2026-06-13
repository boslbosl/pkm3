# ARCHITECTURE — AIVault

**Version:** Canonical v0.4
**Date:** 2026-06-13
**Scope:** Local-first AI session collection, normalization, search, triage, browse, and export.

> **v0.4 additions over v0.3:** Antigravity (IDE + CLI) adapter (§7.4); cross-OS
> discovery between WSL and Windows (§8a); a dependency-free local web frontend
> for navigation/search/grouping with full metadata (§12a). See §19 for the
> review-driven refinements.

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
  discover -> import -> raw store -> normalize -> index -> triage -> browse -> export
        │
        ├── CLI
        ├── local web UI (read-only browse/search, v0.4)
        ├── MCP/API, later
        ├── LLM Wiki export
        ├── Obsidian export
        └── JSONL/Notion-ready export
```

Discovery spans operating systems: from WSL it can reach Windows user profiles,
and from Windows it can reach WSL distros (§8a).

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

### 7.4 Antigravity adapter

Antigravity (Google's agentic IDE, with a CLI) stores local session/agent
history. The exact on-disk format is not contractually stable, so this adapter
is **best-effort and version-tolerant** (§18.1) with the generic folder importer
as fallback.

Input:

- local JSONL/JSON agent logs from the IDE and the CLI
- candidate locations (probed, may evolve):
  - `~/.antigravity/**`, `~/.config/Antigravity/**` (Linux/WSL/macOS)
  - `%APPDATA%/Antigravity/**`, `%LOCALAPPDATA%/Antigravity/**` (Windows)

Output:

- same canonical model as the other coding-agent adapters
- one session per logical conversation where a session id is discoverable,
  otherwise one session per file

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

## 8a. Cross-OS discovery (WSL ↔ Windows)

Native adapters do not hard-code `$HOME`. A `platform_paths` layer enumerates
candidate **home directories** per OS context, and adapters compose their
tool-specific sub-path (e.g. `.claude/projects`, `.codex/sessions`,
`.antigravity`) on top.

```text
platform_paths.home_dirs(os_scope) -> list[(home_path, os_context)]
adapter.discover(os_scope):
    for (home, ctx) in home_dirs(os_scope):
        scan home / <tool subpath> for session files  ->  SourceCandidate(os_context=ctx)
```

`os_scope` selects direction:

| scope | from WSL/Linux | from Windows |
|---|---|---|
| `native` | `~` (current user) | `C:\Users\<me>` |
| `windows` | `/mnt/<drive>/Users/*` | `C:\Users\*` |
| `wsl` | `/home/*` (local distro) | `\\wsl.localhost\<distro>\home\*`, legacy `\\wsl$\...` |
| `all` | union of the above | union of the above |

Rules:

1. Every discovered candidate carries its `os_context`; sessions and raw
   artifacts persist it. The two sides are never silently merged.
2. The original (cross-mount) path is preserved verbatim and feeds the
   `source_fingerprint`, so the same file seen via two mounts dedupes.
3. Discovery and import tolerate unreadable / permission-denied / oddly-encoded
   files: skip and continue, never abort a whole sync.

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

## 12a. Web frontend (local browse/search)

The web UI is a **dependency-free local server** (Python stdlib `http.server`)
plus a small static single-page app. No node build step, no extra runtime
dependencies, no daemon — it starts with `aivault serve` and stops on Ctrl-C.
Bound to `127.0.0.1` by default (local-first; §2 principle 1). Read-only in v0.4.

### Layers

```text
web/api.py     pure functions: Vault -> plain dict payloads (unit-testable, no sockets)
web/server.py  thin HTTP transport: routes /api/* to api.py, serves static files
web/static/    index.html + app.js + style.css (vanilla, no framework)
```

### JSON API

```text
GET /api/stats                          counts + per-source / per-status breakdown
GET /api/projects                       projects with repo root path + session counts
GET /api/sessions?group=&q=&source=&project=&status=&os=&limit=
        group = project | source | time   (time = flat chronological)
        q     = FTS query (same engine as the CLI)
GET /api/session/{id}                   full metadata + messages + snippets
                                        + tags + redaction findings + raw artifact path
```

### Views (same data, three lenses)

1. **By project/repo** — grouped by project root path (repo), sessions sorted by time within each.
2. **By source tool** — grouped by `source_tool` (and `os_context`).
3. **Chronological** — one flat timeline of everything, newest first.

The search box filters whichever view is active using the shared FTS index.
Selecting a session opens a detail panel exposing **all** stored metadata.

---

## 13. CLI commands

MVP CLI:

```bash
aivault init [path]
aivault status
aivault discover [--os-scope native|windows|wsl|all]
aivault detect [--os-scope ...] [--save]      # which agents are sync-able here
aivault config show
aivault config set-sources <agent...>          # pick agents for `sync`
aivault sync [<agent>] [--os-scope ...] [--all] # no arg -> sync configured agents
aivault import-file <path> --source <source>
aivault import-folder <path> --source <source>
aivault list [--source] [--project] [--status]
aivault search <query>
aivault show <session-id>
aivault mark <session-id> <status>
aivault tag <session-id> <tag...>
aivault export llmwiki --status wiki-ready --out <path>
aivault serve [--host 127.0.0.1] [--port 8765]
```

Later CLI:

```bash
aivault cass discover
aivault cass import
aivault redact preview
aivault capsule generate
aivault mcp serve
```

---

## 14. Suggested implementation stack

```text
Python 3.11+
Typer for CLI
Pydantic for canonical models
SQLite + FTS5 for storage/search
Python stdlib http.server + vanilla JS for the local web UI (no build, no deps)
pytest for test fixtures
watchdog later for file watching
FastAPI + React/Tauri later if the UI outgrows the stdlib server
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

---

## 19. Review-driven refinements (v0.4)

Architectural decisions resulting from the PM/Developer/User review (PRD §14):

1. **`platform_paths` indirection** — adapters never hard-code `$HOME`. A single
   module resolves OS-context home directories and powers `--os-scope`, keeping
   cross-OS logic out of every adapter and testable via injected fake roots.
2. **`os_context` is a first-class field** on candidates, sessions, and raw
   artifacts. WSL and Windows views are kept distinct; dedupe still collapses the
   same file seen through two mounts because the original path feeds the
   fingerprint.
3. **Web UI = stdlib server + static SPA.** Chosen over FastAPI/React to honor
   "no daemon, easy install, dependency-free." API logic lives in pure functions
   (`web/api.py`) so it is unit-tested without a socket; the HTTP layer is thin.
4. **Read-only web v0.4.** The UI is a browse/search lens over the DB, not a
   second write path. Triage/write endpoints are a deliberate fast follow once the
   read path is stable, protecting the CLI as the single source of mutations.
5. **Project root (repo path) persisted** so the UI can group by repo, not just by
   the (possibly colliding) folder basename.
6. **Fault-tolerant discovery/import.** Cross-OS scanning must survive permission
   and encoding errors on individual files without aborting a sync.
