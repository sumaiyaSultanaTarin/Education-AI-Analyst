# Multi-Agent Education Document Analyst — Architecture & Planning Spec

**Team size:** 4
**Framework:** LangGraph (orchestration) + FastAPI (backend) + Streamlit (frontend)
**LLM provider:** OpenRouter (free-tier models, multi-model fallback)

---

## 0. Current Implementation Status (as of 2026-08-30)

Sections 1–9 below are the original Phase 0 planning document — kept as the
historical record of decisions made before implementation. Real engineering
tradeoffs shifted some of what was planned; this section is the accurate,
current picture, read this first if you're checking docs against code.

- **Agents:** all 8 (Supervisor + 7 workers) built exactly as planned in §2.2.
- **Two graphs, two different collaboration patterns — not one uniform
  hub.** §5's diagram below shows a single hub-routed flow; the real system
  is two independently compiled graphs with genuinely different shapes:
  - **Intake graph** (`graph/graph_builder.py`): Supervisor-hub, as originally
    designed — `document_ingestion`/`vision_ocr`/`social_intelligence` each
    return to the Supervisor, which routes the next unprocessed document.
  - **Report graph** (`graph/report_graph_builder.py`): a genuine **direct
    chain with no Supervisor node at all** —
    `data_analyst → knowledge_rag → report_generator → qa_critic →
    hitl_approval`, each agent handing off straight to the next. Confirmed
    live from the compiled graph object itself (`.get_graph().draw_mermaid()`),
    not just intended — see the Execution Graph frontend panel.
- **Facebook Graph API:** no longer just the fallback-path placeholder §1
  and §8 describe — genuinely built, tested, and wired into both the
  backend (`POST /sessions/{id}/social/pull-facebook`,
  `tools/fb_graph_api_tools.py`) and the frontend (Dashboard's "Pull
  Facebook data" button), verified live against a real Facebook Page with
  real posts and comments. The CSV-import path (§1, §8) remains available
  as an independent, always-working fallback — not because Graph API failed,
  but because it's a legitimate demo-reliability choice on its own merits.
- **Web search tool** (not in the original plan): added to the Data Analyst
  Agent via the Tavily API (`tools/web_search_tools.py`), pulling real
  external benchmark context into the generated report as its own section.
- **Memory/persistence — simpler than §4's full ERD.** Session state and
  LangGraph checkpoints are persisted to two SQLite files
  (`data/sessions.db`, `data/checkpoints.db`) via `api/session_store.py` —
  no Postgres, and none of §4's `User`/`Institution`/`Teacher`/`TPEScore`
  relational schema was built. §4 is kept below for historical reference
  only; nothing in the running app depends on it. What *is* real: verified
  live surviving both a backend restart and a browser refresh (session ID
  round-trips through the URL, not just server memory).
- **Live execution trace:** confirmed as designed in §6 — no WebSocket/SSE
  stream; the graphs run synchronously to completion within one request, so
  the UI polls instead. A deliberate scope decision, not an oversight.
- **Auth/roles** (§1's first gap): not built — out of scope for the demo,
  every session is anonymous/single-user.

---

## 1. Requirement Analysis & Gaps in the Original Spec

The assignment gives you the *shape* of the system (supervisor + 6 agents, memory, tools, HITL, UI) but leaves several things unspecified that you need to decide before writing code, or you'll end up rebuilding parts of it in week 3.

| Gap | Why it matters | Decision needed |
|---|---|---|
| **Auth / roles** | You have director/dean/associate dean personas — do they see different data or have different approval powers? | Add a `User` + `Role` model now, even if login is a stub in v1. |
| **PII handling** | Student results, teacher evaluations, FB comments are sensitive. | Define what gets stored in plaintext vs redacted, and who can view the Memory Viewer. |
| **Rate limits on free OpenRouter models** | Free models throttle hard and change availability. | Build a model fallback list + retry/backoff from day 1, not as an afterthought. |
| **FB Graph API access** | Scraping FB groups violates ToS; Graph API needs page-admin permission and app review. | Design the Social Intel Agent's input as swappable — Graph API **or** a manual CSV/JSON export — so the demo isn't blocked on Meta approval. |
| **Document versioning / re-ingestion** | Same result sheet might get re-uploaded corrected. | Add a `version` + `superseded_by` field on `Document`. |
| **Concurrency** | 4 people demoing/testing simultaneously will hit the same backend. | Sessions must be isolated by `session_id`, not global state. |
| **Cost ceiling** | Free tier only goes so far. | Track token/cost per session and cap it; show it live in the UI (already required, but decide the *hard cap* behavior — pause vs error). |
| **Embeddings source** | OpenRouter doesn't serve embeddings. | Use a local free embedding model (`sentence-transformers`), not an API, to avoid a second cost/rate-limit dependency. |
| **Testing strategy** | Not mentioned in the spec but graders/team will need it. | Unit tests per tool, integration test per agent, one end-to-end smoke test per phase. |
| **Deployment target** | Local demo vs hosted. | Decide early — affects whether Chroma is local-persistent or needs a hosted vector DB. |

---

## 2. Final Architecture

### 2.1 High-level shape

```
┌─────────────┐      REST + WebSocket      ┌──────────────────────┐
│  Streamlit  │ ─────────────────────────▶ │   FastAPI Backend    │
│  Frontend   │ ◀───────────────────────── │  (session/API layer) │
└─────────────┘      live trace / SSE      └──────────┬───────────┘
                                                        │
                                             ┌──────────▼───────────┐
                                             │   LangGraph Runtime   │
                                             │  (Supervisor + Agents)│
                                             └──────────┬───────────┘
                          ┌────────────────────────────┼────────────────────────────┐
                          ▼                             ▼                            ▼
                 ┌────────────────┐           ┌─────────────────┐          ┌────────────────┐
                 │  Tool Layer     │           │  Memory Layer    │          │  Postgres/SQLite│
                 │ (parsers, OCR,  │           │ Chroma (vectors) │          │ (structured data,│
                 │  FB API, exec)  │           │ + checkpointer   │          │  logs, audit)    │
                 └────────────────┘           └─────────────────┘          └────────────────┘
```

**Why a separate FastAPI backend instead of Streamlit calling LangGraph directly:** with 4 people, you need a clean seam. One pair can build agents/graph behind a stable API contract while another pair builds the UI against that same contract using mocked responses — nobody blocks anyone. It also gives you WebSocket/SSE streaming for the "live execution trace" requirement, which is awkward to do cleanly in a Streamlit-only app.

### 2.2 Agents (8 total — supervisor + 7 workers, above the 6-minimum)

1. **Supervisor Agent** — parses the goal, builds a task plan (ordered/parallel steps), routes via LangGraph conditional edges, aggregates results, decides when to `interrupt()` for human approval.
2. **Document Ingestion Agent** — PDF/DOCX/PPTX/XLSX → structured text/tables.
3. **Vision/OCR Agent** — scanned sheets, screenshots, handwritten forms → text.
4. **Data Analyst Agent** — pandas-based analysis over enrollment/results data (code-execution tool).
5. **Social Intelligence Agent** — FB Graph API (or CSV fallback) → sentiment/topic extraction feeding TPE.
6. **Knowledge/RAG Agent** — owns Chroma; answers cross-document semantic queries for other agents and the final report.
7. **Report Generator Agent** — compiles a DOCX/PPTX report with citations back to source docs.
8. **QA/Critic Agent** — checks the draft report's claims against retrieved source data before it's sent for human approval.

### 2.3 Shared state (LangGraph `StateGraph`)

```python
class AnalystState(TypedDict):
    session_id: str
    goal: str
    plan: list[TaskStep]
    messages: list[AgentMessage]        # agent-to-agent communication log
    documents: list[DocumentRef]
    agent_outputs: dict[str, Any]       # keyed by agent name
    memory_refs: list[str]              # chroma doc ids touched this run
    hitl_status: dict[str, str]         # node_name -> pending/approved/rejected
    token_usage: dict[str, TokenCost]   # keyed by agent/model
    errors: list[ErrorRecord]
```

### 2.4 Memory design

- **Short-term / conversational:** LangGraph `SqliteSaver` checkpointer — per-session, resumable.
- **Long-term / shared knowledge base:** Chroma, **one collection per data type** (`documents`, `results`, `social_posts`) rather than one mixed collection — mixing an Excel row's embedding with a Facebook comment's embedding degrades retrieval quality.
- **Structured/relational:** Postgres (or SQLite for local dev) for anything you need to aggregate, join, or audit — Chroma is bad at "average TPE score per teacher this term"; SQL is not.

---

## 3. Project Folder Structure

```
education-ai-analyst/
├── backend/
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── document_ingestion_agent.py
│   │   ├── vision_ocr_agent.py
│   │   ├── data_analyst_agent.py
│   │   ├── social_intel_agent.py
│   │   ├── knowledge_rag_agent.py
│   │   ├── report_generator_agent.py
│   │   └── qa_critic_agent.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── graph_builder.py
│   │   └── routing.py
│   ├── tools/
│   │   ├── pdf_tools.py
│   │   ├── docx_tools.py
│   │   ├── pptx_tools.py
│   │   ├── xlsx_tools.py
│   │   ├── ocr_tools.py
│   │   ├── fb_graph_api_tools.py
│   │   ├── code_exec_tool.py
│   │   └── rag_tools.py
│   ├── memory/
│   │   ├── chroma_store.py
│   │   └── checkpointer.py
│   ├── db/
│   │   ├── models.py
│   │   ├── schema.sql
│   │   └── migrations/
│   ├── api/
│   │   ├── main.py
│   │   └── routes/
│   │       ├── sessions.py
│   │       ├── documents.py
│   │       ├── memory.py
│   │       ├── hitl.py
│   │       └── trace.py         # WebSocket/SSE
│   ├── core/
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   ├── llm_client.py        # OpenRouter wrapper + fallback list
│   │   └── cost_tracker.py
│   └── tests/
├── frontend/
│   ├── Home.py
│   ├── pages/
│   │   ├── 1_Dashboard.py
│   │   ├── 2_Execution_Trace.py
│   │   ├── 3_Communication_Log.py
│   │   ├── 4_Graph_Viewer.py
│   │   ├── 5_Token_Cost.py
│   │   ├── 6_Logs_Errors.py
│   │   ├── 7_Memory_Viewer.py
│   │   ├── 8_HITL_Controls.py
│   │   └── 9_Final_Report.py
│   ├── components/
│   └── utils/api_client.py
├── data/
│   ├── uploads/
│   ├── chroma_db/
│   └── sample_docs/
├── docs/
│   ├── architecture.md
│   ├── erd.md
│   ├── api_spec.md
│   └── roadmap.md
├── .env.example
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 4. Database ERD (relational store, alongside Chroma)

```
User (id, name, email, role[director|dean|assoc_dean|admin], created_at)
   │ 1
   │ owns
   ▼ N
WorkflowSession (id, user_id FK, goal, status, started_at, ended_at)
   │ 1
   ├── N ── AgentRun (id, session_id FK, agent_name, status, started_at, ended_at,
   │                  tokens_in, tokens_out, cost_usd, model_used)
   │           │ 1
   │           └── N ── AgentMessage (id, run_id FK, from_agent, to_agent, content, timestamp)
   │
   ├── N ── Document (id, session_id FK, filename, type[pdf|docx|pptx|xlsx|image],
   │                  path, version, superseded_by FK->Document.id, ingested_at, status)
   │           │ 1
   │           └── N ── DocumentChunk (id, document_id FK, chroma_id, page_no, text_preview)
   │
   ├── N ── HITLApproval (id, session_id FK, node_name, status[pending|approved|rejected],
   │                       reviewer_id FK->User.id, comment, timestamp)
   │
   ├── N ── Report (id, session_id FK, file_path, format[docx|pptx], generated_at, approved)
   │
   └── N ── ErrorLog (id, session_id FK, agent_name, error_type, message, traceback, timestamp)

Institution (id, name)
   │ 1
   └── N ── Department (id, institution_id FK, name, parent_department_id FK self-ref)
                │ N            [self-ref models director > dean > assoc dean hierarchy]
                ├── N ── Teacher (id, department_id FK, name, fb_page_ref)
                │           │ 1
                │           └── N ── TPEScore (id, teacher_id FK, term, score,
                │                              source_breakdown_json, computed_at)
                └── N ── Student (id, department_id FK, name, enrollment_no)
                            │ 1
                            └── N ── ResultRecord (id, student_id FK, course, term, score)

FacebookSource (id, department_id FK, fb_page_or_group_id, name, permission_status)
   │ 1
   └── N ── SocialPost (id, source_id FK, fb_post_id, content, posted_at)
               │ 1
               └── N ── SocialComment (id, post_id FK, fb_comment_id, author, content, sentiment_score)
```

**Design note:** `Department` is self-referencing to model director → dean → associate dean without hardcoding levels — you can add or remove a tier without a schema change.

---

## 5. LangGraph Workflow Diagrams

Superseded by §0 above once real vs. planned diverged — kept here as the
original single-graph design intent. The two diagrams below are what's
actually compiled and running today, pulled directly from each graph's own
`.get_graph().draw_mermaid()` (also what the Execution Graph frontend panel
renders live, so these can't drift from the real code the way a hand-drawn
diagram could).

**Intake graph** (`graph/graph_builder.py`) — Supervisor as a hub:

```mermaid
graph TD
    Start([Uploaded documents]) --> Supervisor
    Supervisor -->|pdf/docx/pptx/xlsx| DocIngest[Document Ingestion Agent]
    Supervisor -->|image| OCR[Vision/OCR Agent]
    Supervisor -->|social_csv| Social[Social Intelligence Agent]
    DocIngest --> Supervisor
    OCR --> Supervisor
    Social --> Supervisor
    Supervisor -->|all documents processed| IntakeEnd([intake complete])
```

**Report graph** (`graph/report_graph_builder.py`) — a genuine direct chain,
**no Supervisor node in this graph at all**:

```mermaid
graph TD
    IntakeEnd([intake complete]) --> DataAnalyst[Data Analyst Agent]
    DataAnalyst --> RAG[Knowledge/RAG Agent]
    RAG --> ReportGen[Report Generator Agent]
    ReportGen --> QA[QA/Critic Agent]
    QA -->|issues found| ReportGen
    QA -->|passes checks| HITL{{Human-in-the-Loop\napproval - interrupt()}}
    HITL -->|approved| Finalize([Final report delivered])
    HITL -->|rejected/retry| ReportGen
```

Two deliberately different collaboration shapes for two different problems:
the intake phase routes documents by type to whichever worker handles that
type, which is naturally a dispatch problem — a hub fits. The report phase
is an inherently sequential pipeline (each stage needs the previous stage's
output), so it's wired as what it actually is: agents handing off directly to
each other, no hub in between. Neither is a compromise; each fits its half of
the problem.

---

## 6. API Specification (FastAPI backend)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/sessions` | Create a session: `{goal, user_id}` → `session_id` |
| `POST` | `/sessions/{id}/documents` | Upload a document (multipart) |
| `POST` | `/sessions/{id}/run` | Kick off the LangGraph run for this session |
| `GET` | `/sessions/{id}` | Session status, current node, plan |
| `WS` | ~~`/sessions/{id}/trace`~~ | **Not implemented** — the intake/report graphs run synchronously to completion within one request (see `graph_builder.py`, `report_pipeline.py`) and don't emit incremental node-enter/exit events yet. `GET /sessions/{id}/messages` below is polled instead. |
| `GET` | `/sessions/{id}/messages` | Agent-to-agent communication log — implemented (`api/routes/observability.py`) |
| `GET` | `/sessions/{id}/graph` | Mermaid source for both compiled graphs, for the Graph Viewer — implemented (`api/routes/observability.py`) |
| `GET` | `/sessions/{id}/cost` | Token usage + cost breakdown per LLM call — implemented (`api/routes/observability.py`); only `qa_critic`/`vision_ocr` call an LLM, and every fallback model is free-tier so `cost_usd` is genuinely `$0.00` today |
| `GET` | `/sessions/{id}/errors` | Structured error log — reused from `GET /sessions/{id}`'s `errors` field instead of a dedicated route (no separate error store exists) |
| `POST` | `/sessions/{id}/hitl/{node}/approve` | Resume a paused graph |
| `POST` | `/sessions/{id}/hitl/{node}/reject` | Reject + optional edit instructions |
| `POST` | `/sessions/{id}/hitl/{node}/retry` | Re-run the failed/paused node |
| `GET` | `/sessions/{id}/memory?query=` | Query the Chroma knowledge base for this session |
| `GET` | `/sessions/{id}/report` | Fetch the final generated file |

All endpoints scoped by `session_id` so 4 teammates (or many end users) can run concurrent sessions without state collisions.

---

## 7. Development Roadmap (suggested for 4 people)

**Role split:**
- **A — Backend/Infra Lead:** FastAPI, DB schema + migrations, logging, cost tracker, deployment
- **B — Agent/Graph Lead:** LangGraph state, Supervisor, routing, checkpointer, HITL wiring
- **C — Domain Agents Lead:** Document/OCR/Data/Social/RAG/Report/QA agents + their tools
- **D — Frontend/UX Lead:** Streamlit app (all 9 panels), API client, mocked-then-real integration

| Phase | Weeks | A | B | C | D |
|---|---|---|---|---|---|
| 0 — Planning | 0.5 | This doc — reviewed and signed off by all 4 | | | |
| 1 — Skeleton | 1 | FastAPI scaffold, DB schema, OpenRouter client + fallback | LangGraph state schema, Supervisor stub, checkpointer | Tool stubs (parsers, no LLM yet) | Streamlit shell hitting mocked API |
| 2 — Core agents | 1.5 | Logging, cost tracker wired in | Routing logic for 3 core agents | Document Ingestion + Vision/OCR agents (real) | Dashboard + Execution Trace panels against real WS |
| 3 — Data & memory | 1.5 | Postgres models finalized | Chroma integration in graph | Data Analyst + Knowledge/RAG agents (real) | Memory Viewer + Token/Cost panels |
| 4 — Social + report | 1.5 | Error handling hardened | HITL `interrupt()` wired end-to-end | Social Intel + Report Generator + QA/Critic agents | Communication Log + HITL Controls + Graph Viewer |
| 5 — Integration | 1 | All | All | All | All — end-to-end run, bug bash |
| 6 — Polish/demo | 0.5 | Deployment | Failure-mode demo script | Sample data + FB fallback CSV | Final Report viewer polish, screenshots/video |

Weekly sync recommended: 30 min, each person demos their lane against the shared API contract from Phase 1 so integration in Phase 5 isn't a surprise.

---

## 8. Key Technical Decisions Explained

- **LangGraph over CrewAI/AutoGen:** you need cycles (worker → supervisor → next worker), native `interrupt()` for human-in-the-loop, and built-in checkpointing/persistence — CrewAI's process model and AutoGen's conversational pattern make explicit pause/resume and fine-grained routing more awkward to implement cleanly.
- **FastAPI backend separate from Streamlit:** required for real parallel team work and for WebSocket-based live trace streaming, which is the cleanest way to satisfy the "live agent execution trace" UI requirement.
- **Chroma + a relational DB, not Chroma alone:** vector search answers "what does the record say about X," but director-level questions ("average TPE by department this term") need SQL aggregation — Chroma isn't built for that.
- **Local embeddings (`sentence-transformers`) instead of an API:** OpenRouter doesn't serve embeddings, and adding a second paid/rate-limited API just for embeddings is an avoidable dependency given free-tier constraints.
- **OpenRouter with a model fallback list, not a single model:** free-tier models on OpenRouter throttle and occasionally go unavailable; the LLM client should try a short ordered list of free models with retry/backoff rather than hard-failing on one.
- **FB Graph API with a CSV/JSON fallback path:** keeps the Social Intelligence Agent demoable even if Meta app review isn't done in time, and keeps you clearly on the compliant side of FB's platform terms. Both paths are real and working (see §0) — CSV import stays the default for demo reliability, not because Graph API is unfinished.
- **Supervisor as a hub for intake, a direct chain for the report pipeline — not one uniform pattern.** The original plan assumed a Supervisor-hub throughout; what actually got built (see §0, §5) splits by problem shape: intake is a type-based dispatch problem (a hub fits), the report pipeline is an inherently sequential one (a direct chain fits, and is what's actually running — zero Supervisor involvement in that graph). Adding worker #9 to the intake side still doesn't require touching another agent's code; the report side's agents already only need to know about their immediate predecessor's output shape.
- **Web search as a fourth tool alongside RAG/APIs/Python:** not in the original plan — added to the Data Analyst Agent (Tavily) once it became clear "Tool Integration" as graded wanted web search specifically named, not just implied by RAG. Feeds real external context into the generated report as its own section, not a side computation that gets thrown away.

---

## 9. Next Step

Once your team signs off on this doc, implementation starts at **Phase 1** — I'd suggest we build the LangGraph state schema + Supervisor stub and the FastAPI session scaffold first, since everything else (both agent work and UI work) depends on that contract being stable.
