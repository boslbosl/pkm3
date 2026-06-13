# START_HERE — AIVault Implementation Guide

**Status:** Canonical v0.3  
**Use these files only:** `PRD.md`, `ARCHITECTURE.md`, `START_HERE.md`  
**Ignore older duplicate files:** previous `prd.md`, `architecture.md`, `ARCHITECUTRE.md`, and older zip packages are superseded.

---

## 1. What are we building?

AIVault is a **local-first AI session collector and curation layer**.

It collects or imports sessions from:

- ChatGPT official export / browser export
- Claude official export / Claude Desktop export
- Perplexity manual/export/Notion-based export
- Claude Code local JSONL logs
- Codex CLI/Desktop/WSL local logs
- Cursor local storage or exported conversations
- Cline task history
- SpecStory Markdown history
- Optional CASS bridge

Then it normalizes them into one local vault:

```text
raw evidence -> normalized sessions -> search index -> triage inbox -> LLM Wiki/Obsidian/Notion/MCP export
```

AIVault is **not** an LLM Wiki compiler. It prepares high-quality, deduplicated, redacted, wiki-ready source material for an LLM Wiki system.

---

## 2. Do we implement both old PRDs?

No.

The earlier files were draft variants. They are not separate products or separate implementation tracks.

Implement only the canonical v0.3 scope:

```text
AIVault Core
  + source adapters
  + immutable raw store
  + canonical session schema
  + SQLite/FTS index
  + inbox/triage workflow
  + redaction preview
  + LLM Wiki-compatible export
  + optional CASS bridge
```

---

## 3. Implementation strategy

Use a **greenfield core**.

Do not fork Pratiyush/llm-wiki or CASS as the core product.

Use existing projects as integrations:

| Existing project/tool | Role in AIVault |
|---|---|
| Pratiyush/llm-wiki | Downstream export target |
| CASS | Optional external bridge for coding-agent session discovery/search/export |
| SpecStory | Markdown source adapter |
| AI Toolbox / AI Exporter | Web-chat export source |
| Pactify / Notion export | Optional Perplexity/web-chat source |
| Notion MCP | Optional downstream workspace access |

---

## 4. Start with the vertical slice

Do not start with every source.

Build one end-to-end path first:

```text
Claude Code JSONL + Codex JSONL
        -> import
        -> normalize
        -> search
        -> triage status
        -> export to llm-wiki-compatible Markdown
```

This proves the core architecture before adding ChatGPT, Perplexity, Cursor, Cline, or CASS.

---

## 5. Recommended MVP order

### Phase 1 — Local vault foundation

Deliverables:

- `aivault init`
- local vault directory creation
- SQLite database creation
- raw artifact store
- canonical session/message tables
- SHA-256 based dedupe

Commands:

```bash
aivault init ~/ai-vault
aivault status
```

---

### Phase 2 — Native coding-agent adapters

Start with:

1. Claude Code JSONL
2. Codex JSONL

Then add:

3. Cline task history
4. Cursor local/export adapter
5. SpecStory Markdown adapter

Commands:

```bash
aivault discover
aivault sync claude-code
aivault sync codex
aivault list
```

---

### Phase 3 — Search and session view

Deliverables:

- SQLite FTS5 index
- CLI search
- session detail view
- project/agent/date filters

Commands:

```bash
aivault search "auth refresh token"
aivault show <session-id>
aivault list --project myrepo --agent claude-code
```

---

### Phase 4 — Triage workflow

Deliverables:

- status field: `new`, `reviewed`, `keep`, `ignore`, `wiki_ready`, `exported`
- tags
- notes
- important-session marker
- manual project override

Commands:

```bash
aivault mark <session-id> keep
aivault mark <session-id> wiki-ready
aivault tag <session-id> auth refactor bugfix
```

---

### Phase 5 — LLM Wiki export

Deliverables:

- Markdown export compatible with downstream LLM Wiki tools
- source frontmatter
- raw evidence link
- session capsule generation
- export manifest

Commands:

```bash
aivault export llmwiki --status wiki-ready --out ~/llm-wiki/raw/sessions
aivault export obsidian --status keep --out ~/Obsidian/AIVault
```

---

### Phase 6 — Web/export sources

Add importers for:

- ChatGPT official export zip
- Claude official export
- Markdown/JSON folders from AI Toolbox or AI Exporter
- Notion/Markdown export from Pactify-style workflows
- manual Perplexity export folder

Commands:

```bash
aivault import chatgpt-export.zip
aivault import claude-export.zip
aivault import-folder ~/Downloads/ai-exports --source web-export
```

---

### Phase 7 — Optional CASS bridge

CASS should be an optional bridge, not the source of truth.

Commands:

```bash
aivault cass discover
aivault cass import --workspace ~/dev/myrepo
aivault cass search "migration bug"
```

AIVault should store imported CASS results in its own raw store and canonical schema.

---

## 6. Suggested tech stack

Recommended initial stack:

```text
Language: Python 3.11+
CLI: Typer
DB: SQLite + FTS5
Parsing: Pydantic models
Local API/UI later: FastAPI + React or Tauri
File watching later: watchdog
Packaging: uv or poetry
Testing: pytest
```

Reason: fast iteration, good filesystem parsing, simple subprocess integration with CASS, easy SQLite/FTS usage.

---

## 7. Minimal repo structure

```text
aivault/
  pyproject.toml
  README.md
  docs/
    PRD.md
    ARCHITECTURE.md
    START_HERE.md
  src/aivault/
    cli.py
    config.py
    db.py
    models.py
    raw_store.py
    dedupe.py
    search.py
    adapters/
      base.py
      claude_code.py
      codex.py
      specstory.py
      folder_import.py
      cass_bridge.py
    exporters/
      llmwiki.py
      obsidian.py
      jsonl.py
  tests/
    fixtures/
    test_claude_code_adapter.py
    test_codex_adapter.py
    test_dedupe.py
    test_llmwiki_export.py
```

---

## 8. MVP acceptance criteria

MVP is complete when:

1. `aivault init` creates a local vault.
2. Claude Code and Codex sessions can be discovered and imported.
3. Imported sessions preserve raw evidence.
4. Sessions are normalized into a common schema.
5. Search works across imported sessions.
6. User can mark sessions as `wiki_ready`.
7. `aivault export llmwiki` produces Markdown files with metadata and raw-source references.
8. Re-running sync does not duplicate sessions.

---

## 9. First coding task

Implement this first:

```bash
aivault init ~/ai-vault
aivault import-file ./fixtures/claude-code-session.jsonl --source claude-code
aivault list
aivault show <session-id>
aivault export llmwiki --out ./out/llmwiki
```

Do not implement UI, embeddings, Notion, MCP, or all adapters before this works.
