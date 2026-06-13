# PRD: AI Session Vault

**문서 상태:** Draft v0.2  
**작성일:** 2026-06-12  
**제품명:** AI Session Vault, 임시명 `aivault`  
**제품 유형:** Local-first AI session collector, inbox, search, triage, LLM Wiki export layer  
**주 사용자:** 여러 AI coding agent와 web AI를 병행 사용하는 개인 개발자, vibe coding 사용자, 소규모 개발팀  
**핵심 결정:** Greenfield로 개발하되, CASS는 optional bridge/adapter로 활용한다. CASS를 fork하거나 core DB로 삼지 않는다.

---

## 1. 배경

AI 도구를 여러 개 쓰는 개발자는 실제 작업 지식이 다음 위치에 흩어진다.

- ChatGPT, Claude, Perplexity 같은 web/desktop AI 대화
- Codex CLI/Desktop, Claude Code, Cursor, Cline 같은 coding-agent 세션 로그
- Windows native, WSL, macOS, Linux에 각각 분리된 home/config/history 경로
- JSONL, SQLite, Markdown, HTML, 공식 export zip, Notion DB 등 서로 다른 저장 포맷
- agent가 중간에 만든 계획, 오류 분석, 테스트 결과, 의사결정, 파일 변경 맥락

이 정보는 나중에 재사용 가치가 높지만, 기본 상태에서는 다음 문제가 있다.

1. **찾기 어렵다.** 어떤 agent에서 해결했는지 기억하지 못하면 검색이 끊긴다.
2. **세션 단위 구조가 약하다.** 프로젝트, 목표, 변경 파일, 명령어, 결정사항, 실패 원인을 한눈에 보기 어렵다.
3. **LLM Wiki로 바로 넣기에는 노이즈가 많다.** raw transcript 전체를 wiki에 넣으면 중복, tool output, 실패 로그가 과다해진다.
4. **수동 export만으로는 누락된다.** 세션 종료 시마다 사람이 export하는 방식은 장기 운영에 약하다.
5. **자동 수집만으로는 품질이 낮다.** 모든 raw log를 모아도 “중요한 세션”과 “wiki-ready 세션”을 구분해야 한다.

---

## 2. 왜 CASS가 후보로 나왔는가

CASS, 즉 `coding_agent_session_search`, 는 여러 coding-agent 세션을 로컬에서 찾아 인덱싱하고 검색하는 TUI/CLI 도구다. CASS README 기준으로 Codex, Claude Code, Gemini CLI, Cline, OpenCode, Amp, Cursor, ChatGPT, Aider, GitHub Copilot Chat, Copilot CLI 등 다수의 local agent history를 하나의 searchable timeline으로 모은다.

CASS가 갑자기 등장한 이유는 간단하다.

```text
당신의 문제: 여러 AI agent 세션을 자동/반자동으로 수집해서 LLM Wiki화하고 싶다.
CASS의 강점: 여러 local coding-agent history를 자동 discovery, normalize, index, search한다.
```

다만 CASS는 `aivault`의 대체품이 아니다.

| 항목 | CASS | aivault가 만들어야 하는 영역 |
|---|---|---|
| 주요 목적 | local coding-agent session search | 수집함, 정규화, triage, redaction, LLM Wiki export |
| UI | TUI/CLI 중심 | local web UI + CLI + MCP |
| 데이터 철학 | SQLite archive + search index | immutable raw store + canonical session DB + export workflow |
| 검토 상태 | 검색/보기 중심 | new/reviewed/keep/wiki-ready/exported 상태 관리 |
| Wiki 변환 | 일부 export/pack 가능 | LLM Wiki schema와 capsule export를 1급 기능으로 제공 |
| web AI export | 일부 local ChatGPT app storage 가능 | 공식 export zip, browser export, Notion/Pactify export까지 수용 |

따라서 CASS는 다음 세 가지 방식으로 활용한다.

1. **Discovery bridge:** 사용자의 환경에 어떤 agent 세션이 있는지 빠르게 탐지한다.
2. **Search bridge:** 기존 CASS index를 활용해 cross-agent 검색을 제공한다.
3. **Backfill bridge:** CASS가 읽을 수 있는 세션을 Markdown/JSON으로 export하여 `aivault` raw store에 import한다.

반대로 다음은 하지 않는다.

- CASS를 fork해서 제품 core로 삼지 않는다.
- CASS SQLite DB를 `aivault`의 source of truth로 삼지 않는다.
- CASS 라이선스 rider 검토 없이 코드를 복사하거나 배포물에 내장하지 않는다.

---

## 3. 제품 비전

`aivault`는 여러 AI 도구의 대화와 coding-agent 세션을 **로컬-first 세션 수집함**으로 모으고, LLM Wiki로 보내기 전에 사람이 검토·선별·정리할 수 있게 하는 제품이다.

최종 사용자 경험은 다음과 같다.

```text
1. aivault가 로컬 agent 세션과 export 파일을 발견한다.
2. 사용자는 세션을 프로젝트, agent, 날짜, 파일, 명령어, 주제별로 본다.
3. 중요한 세션을 keep / summarize / wiki-ready / ignore로 분류한다.
4. 민감정보를 redaction preview로 확인한다.
5. 선택한 세션을 LLM Wiki raw source, inbox capsule, Obsidian note, Notion export로 내보낸다.
6. Claude Code, Codex, Cursor, Cline 같은 agent는 MCP/CLI로 과거 세션을 검색해 재사용한다.
```

---

## 4. 포지셔닝

| 도구 유형 | 대표 예 | 강점 | 부족한 점 | aivault의 위치 |
|---|---|---|---|---|
| LLM Wiki compiler | Pratiyush/llm-wiki | raw session을 wiki/site/llms.txt로 변환 | source discovery, triage, redaction, import batch 관리가 약함 | LLM Wiki 앞단의 collector/inbox layer |
| 세션 검색기 | CASS | 여러 coding-agent 세션 자동 discovery/search | 제품형 review queue, LLM Wiki export workflow는 별도 | optional bridge로 활용 |
| terminal session recorder | SpecStory | terminal coding-agent 세션을 Markdown으로 기록 | web AI, Cline, desktop/export zip은 별도 | Markdown source adapter |
| browser export extension | AI Toolbox, AI Exporter | ChatGPT/Claude/Gemini 등 web 대화 export | local coding agent 로그 미지원 | web/export import source |
| Notion sync | Pactify, Notion MCP | Notion 중심 knowledge hub | raw source of truth와 local vault 구조가 약함 | optional source/downstream connector |

---

## 5. 목표와 비목표

## 5.1 MVP 목표

1. 로컬 vault 생성 및 관리
2. source discovery와 import batch 관리
3. Claude Code, Codex, Cursor, Cline, SpecStory, CASS bridge import 지원
4. ChatGPT/Claude/Perplexity export 파일 import 지원
5. canonical session schema 생성
6. SQLite + FTS 기반 검색
7. session inbox UI 제공
8. 상태 관리: `new`, `reviewed`, `keep`, `ignore`, `wiki-ready`, `exported`
9. dedupe, provenance, raw hash 추적
10. basic redaction preview
11. LLM Wiki 호환 Markdown export
12. agent-readable CLI/MCP search endpoint

## 5.2 비목표

1. LLM Wiki compiler 자체를 재구현하지 않는다.
2. ChatGPT/Claude/Perplexity 웹사이트를 비공식 scraping으로 강제 수집하지 않는다.
3. 원본 agent 로그를 수정하지 않는다.
4. Notion을 source of truth로 삼지 않는다.
5. 초기 버전에서 cloud sync, team auth, multi-user permission을 구현하지 않는다.
6. CASS 코드를 복사해 내장하지 않는다.

---

## 6. 사용자 페르소나

## 6.1 개인 vibe coder

- ChatGPT, Claude, Codex, Claude Code, Cursor, Cline을 병행 사용한다.
- 같은 문제를 여러 agent에게 반복 설명한다.
- 과거 세션에서 이미 해결한 오류, 명령어, 설계 결정을 다시 찾고 싶다.
- Obsidian 또는 Markdown vault를 선호한다.

## 6.2 소규모 개발팀 리드

- 여러 팀원이 각자 다른 AI agent를 사용한다.
- “왜 이렇게 구현했는지”에 대한 rationale이 PR이나 issue에 남지 않는다.
- coding-agent session을 장기적인 project memory로 만들고 싶다.
- 민감정보 유출을 우려해 local-first를 선호한다.

## 6.3 agent-heavy power user

- Claude Code, Codex, Cursor, Cline 세션을 여러 OS와 WSL에서 동시에 사용한다.
- terminal에서 빠른 검색과 handoff pack을 원한다.
- CASS를 이미 쓰거나 CASS류 기능을 선호한다.
- LLM Wiki, llms.txt, MCP를 통해 agent가 과거 지식을 읽게 하고 싶다.

---

## 7. 지원 source 범위

## 7.1 MVP 자동 수집 대상

| Source | 방식 | 우선순위 | 비고 |
|---|---|---:|---|
| Claude Code | JSONL path scan/watch | P0 | Windows/WSL/macOS source instance 분리 |
| Codex CLI | JSONL path scan/watch | P0 | Windows/WSL source instance 분리 |
| Cline | VS Code global storage/task directory import | P0 | path 변동 가능성 때문에 adapter versioning 필요 |
| Cursor | SQLite/global + workspace storage import | P0 | DB lock, schema drift 대응 필요 |
| SpecStory | `.specstory/history/*.md` import | P1 | Markdown parser |
| CASS bridge | external CLI JSON/Markdown import | P1 | user-installed CASS만 호출 |

## 7.2 MVP export/import 기반 대상

| Source | 방식 | 우선순위 | 비고 |
|---|---|---:|---|
| ChatGPT | official export zip / Markdown export folder | P0 | 공식 export 우선 |
| Claude web/desktop | official export / Markdown export folder | P0 | 공식 export 우선 |
| Perplexity | Markdown/HTML/manual export, Pactify/Notion export | P1 | 자동 scraping 금지 |
| Notion | Notion export zip/Markdown folder | P2 | Pactify output 흡수 용도 |

---

## 8. 핵심 기능 요구사항

## 8.1 Vault 초기화

### User story

사용자는 한 번의 명령으로 local vault를 만들고 기본 디렉터리와 DB를 생성한다.

```bash
aivault init ~/ai-vault
```

### Acceptance criteria

- `raw/`, `inbox/`, `normalized/`, `exports/`, `.aivault/`가 생성된다.
- SQLite DB가 생성된다.
- 기본 ignore/redaction rule 파일이 생성된다.
- vault config가 생성된다.

---

## 8.2 Source discovery

### User story

사용자는 로컬 환경에 존재하는 AI session source를 자동 탐지한다.

```bash
aivault sources discover --include-wsl
```

### Acceptance criteria

- Windows native와 WSL source를 분리해서 보여준다.
- source별 상태가 `available`, `missing`, `permission-denied`, `needs-export`, `unsupported`로 표시된다.
- CASS가 설치되어 있으면 `cass_bridge` source를 제안한다.
- source별 estimated session count를 제공한다.

---

## 8.3 Import batch

### User story

사용자는 발견된 source 또는 export 파일을 vault에 import한다.

```bash
aivault sync claude-code --instance wsl
aivault import ~/Downloads/chatgpt-export.zip
aivault import .specstory/history
aivault import-cass --agent codex --since 30d
```

### Acceptance criteria

- 모든 import는 `import_batch_id`를 가진다.
- import 결과는 added/updated/skipped/failed/duplicated count를 반환한다.
- 원본 파일은 hash 기반으로 raw store에 복사된다.
- parser error는 session 전체 실패가 아니라 artifact-level error로 기록된다.

---

## 8.4 Canonical session normalization

### User story

서로 다른 source 포맷을 같은 session schema로 변환한다.

### Acceptance criteria

- 각 session은 최소한 `id`, `source_tool`, `source_instance`, `title`, `project`, `started_at`, `messages`, `raw_artifacts`를 가진다.
- message role은 `user`, `assistant`, `system`, `tool`, `unknown` 중 하나로 정규화된다.
- tool call, command, file reference, error snippet은 별도 derived field로 추출된다.
- 원문 raw artifact hash와 parser version이 유지된다.

---

## 8.5 Search

### User story

사용자는 모든 source를 한 번에 검색한다.

```bash
aivault search "auth refresh token bug" --agent codex --project myrepo
```

### Acceptance criteria

- SQLite FTS5 기반 lexical search를 제공한다.
- agent, project, date, status, source_instance로 필터링한다.
- 검색 결과는 source, session, message, snippet, score, timestamp를 포함한다.
- CASS bridge가 활성화된 경우 CASS search result를 보조 evidence로 병합할 수 있다.

---

## 8.6 Inbox / triage UI

### User story

사용자는 새로 들어온 세션을 수집함에서 검토한다.

### Acceptance criteria

- 세션 리스트는 agent, project, date, title, message count, file refs, command count, status를 보여준다.
- bulk action으로 `keep`, `ignore`, `wiki-ready` 지정이 가능하다.
- session detail에서 raw transcript, normalized messages, extracted entities를 전환해서 볼 수 있다.
- duplicate group과 likely-related sessions를 보여준다.

---

## 8.7 Redaction preview

### User story

사용자는 export 전에 민감정보 후보를 확인한다.

### Acceptance criteria

- API key, token, email, file path, env var, URL secret 후보를 탐지한다.
- redaction은 raw를 수정하지 않고 export view에만 적용한다.
- 사용자는 rule을 승인/무시할 수 있다.
- redaction log가 남는다.

---

## 8.8 LLM Wiki export

### User story

사용자는 `wiki-ready` 세션을 LLM Wiki ingest에 적합한 Markdown으로 내보낸다.

```bash
aivault export llmwiki --status wiki-ready --target ~/llm-wiki/raw/sessions
```

### Acceptance criteria

- source별 Markdown 파일을 생성한다.
- YAML frontmatter에 provenance, source_tool, project, timestamps, hashes, status를 포함한다.
- 원문 전체 transcript export와 capsule export를 분리한다.
- export manifest가 생성된다.
- 같은 세션을 재export하면 deterministic path와 diff-friendly output을 유지한다.

---

## 8.9 Agent-readable interface

### User story

Claude Code, Codex, Cursor, Cline이 과거 세션을 검색하고 handoff context를 가져온다.

```bash
aivault agent search "checkout timeout" --json --limit 5
aivault agent pack "checkout timeout root cause" --max-tokens 6000 --json
```

### Acceptance criteria

- stdout은 JSON만 출력하고 diagnostics는 stderr로 분리한다.
- token budget을 적용한다.
- 모든 evidence에 source session 링크와 raw provenance를 포함한다.
- MCP server는 read-only tools만 제공한다.

---

## 9. 상태 모델

```text
new
  ├── reviewed
  │     ├── keep
  │     │     └── wiki-ready
  │     │             └── exported
  │     └── ignore
  └── quarantined
```

| 상태 | 의미 |
|---|---|
| `new` | import되었지만 검토 전 |
| `reviewed` | 사람이 한 번 확인함 |
| `keep` | 장기 보존 가치 있음 |
| `wiki-ready` | LLM Wiki에 넣을 가치 있음 |
| `exported` | 최소 1회 export됨 |
| `ignore` | 검색/위키 대상에서 제외 |
| `quarantined` | parsing error, 민감정보 과다, 손상 파일 등 |

---

## 10. 데이터 품질 요구사항

1. 동일 세션 중복 import 방지
2. 동일 transcript가 여러 source에서 들어온 경우 duplicate group으로 묶기
3. source path, hash, parser version, import batch 추적
4. raw immutable 원칙 유지
5. export 재현성 보장
6. Windows/WSL path alias 관리
7. large session truncation 없이 raw 보존, UI/agent view에서만 truncation

---

## 11. 보안 및 개인정보 요구사항

1. 기본값은 네트워크 전송 없음
2. raw store는 local filesystem에 저장
3. 모든 source adapter는 read-only
4. export 전 redaction preview 제공
5. secret scanning rule 제공
6. MCP tools는 read-only로 시작
7. config에 민감정보 저장 금지
8. cloud sync는 MVP 제외
9. CASS bridge는 사용자가 설치한 binary만 호출하고, binary를 번들하지 않는다.

---

## 12. CASS bridge 요구사항

## 12.1 목적

CASS를 `aivault`의 optional external provider로 사용한다.

```text
CASS = discovery/search/backfill helper
aivault = source of truth, inbox, triage, export product
```

## 12.2 기능

| 기능 | 명령 예 | aivault 처리 |
|---|---|---|
| health check | `cass triage --json` | CASS 사용 가능 여부 판단 |
| full index | `cass index --full --json` | 사용자가 명시적으로 실행할 때만 호출 |
| session list | `cass sessions --json` | source 후보로 import |
| workspace sessions | `cass sessions --workspace <path> --json` | project mapping 보조 |
| export | `cass export <session> --format json` | raw artifact로 import |
| search | `cass search <query> --robot` | federated search evidence로 병합 |
| pack | `cass pack <query> --robot` | agent handoff 후보로 사용 |

## 12.3 제약

- CASS DB는 derived index로 취급한다.
- CASS result만 있고 원본 artifact가 없으면 provenance quality를 `derived-only`로 표시한다.
- CASS path가 Windows/WSL을 가리킬 수 있으므로 path normalization을 거친다.
- CASS 라이선스 rider 때문에 fork/copy/bundling은 별도 검토 전 금지한다.

---

## 13. MVP 화면

## 13.1 Sources

- source name
- type: direct / export / cass_bridge / folder
- OS/runtime: windows / wsl / macos / linux
- path
- health
- last sync
- sessions found
- sessions imported
- errors

## 13.2 Inbox

- session title
- agent
- project
- started_at
- status
- files touched
- commands
- error count
- duplicate indicator
- sensitivity indicator

## 13.3 Session detail

- summary panel
- transcript view
- extracted files/commands/errors
- raw artifact list
- related sessions
- redaction preview
- export actions

## 13.4 Exports

- export target
- status filter
- last export time
- files generated
- manifest
- diff preview

---

## 14. CLI MVP

```bash
# setup
aivault init ~/ai-vault
aivault doctor

# discovery
aivault sources discover --include-wsl
aivault sources list

# import/sync
aivault sync claude-code --instance windows
aivault sync claude-code --instance wsl
aivault sync codex --instance wsl
aivault sync cursor
aivault sync cline
aivault import ~/Downloads/chatgpt-export.zip
aivault import ~/Downloads/claude-export.zip
aivault import .specstory/history

# CASS bridge
aivault cass health
aivault cass import --since 30d
aivault cass search "auth bug" --json

# search/triage
aivault search "auth refresh" --project myrepo
aivault sessions list --status new
aivault sessions mark <id> --status wiki-ready

# export
aivault export llmwiki --status wiki-ready --target ~/llm-wiki/raw/sessions
aivault export obsidian --status keep --target ~/obsidian/AI-Sessions
aivault agent pack "checkout redirect timeout" --json --max-tokens 6000
```

---

## 15. 성공 지표

## 15.1 MVP 지표

- 첫 실행 후 5분 이내 source discovery 완료
- Claude Code, Codex, Cursor, Cline 중 최소 3개 source에서 세션 import 성공
- ChatGPT 또는 Claude official export zip import 성공
- 1,000개 세션 기준 검색 응답 300ms 이내
- duplicate false positive 5% 이하
- LLM Wiki export 결과가 deterministic path를 유지
- raw artifact 손상/수정 0건

## 15.2 제품 지표

- 사용자가 매주 wiki-ready로 표시하는 세션 수
- 과거 세션 검색 후 새 agent 작업에 재사용한 횟수
- 중복 질문 감소율
- LLM Wiki ingest 성공률
- redaction preview에서 탐지된 secret 후보 수

---

## 16. 주요 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| agent 로그 포맷 변경 | parser 실패 | adapter versioning, parser tests, quarantine |
| Windows/WSL path 혼선 | 중복/누락 | source_instance, path alias table |
| DB lock | Cursor/Cline import 실패 | read-only copy 후 parse |
| 민감정보 export | 보안 사고 | redaction preview, export block rule |
| CASS 의존 과다 | 제품 통제력 저하 | CASS는 optional bridge로 제한 |
| CASS 라이선스 rider | 배포/상업화 리스크 | code copy/fork 금지, legal review |
| web AI scraping 불안정 | 계정/정책 리스크 | 공식 export/import fallback 우선 |

---

## 17. 출시 범위

## 17.1 v0.1 CLI MVP

- vault init
- source discovery
- Claude Code/Codex direct import
- ChatGPT/Claude export zip import
- SQLite + FTS search
- status mark
- LLM Wiki export

## 17.2 v0.2 Collector MVP

- Cursor/Cline direct import
- CASS bridge
- SpecStory import
- local web inbox UI
- duplicate group
- redaction preview

## 17.3 v0.3 Agent memory MVP

- MCP read-only server
- agent pack
- session capsule generation
- Obsidian export
- Notion export/import folder support

---

## 18. 최종 제품 방향

`aivault`는 CASS나 Pratiyush/llm-wiki를 대체하지 않는다. 역할은 다음과 같이 분리한다.

```text
CASS
  = local coding-agent history discovery/search helper

Pratiyush/llm-wiki
  = downstream LLM Wiki compiler/static site generator

aivault
  = source collector + session inbox + triage + redaction + export pipeline
```

따라서 제품 개발 전략은 다음이다.

```text
Greenfield core
+ CASS optional bridge
+ direct adapters for key sources
+ export fallback for web AI
+ LLM Wiki compatible outputs
```
