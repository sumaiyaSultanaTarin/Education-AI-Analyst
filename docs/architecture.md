# Multi-Agent Education Document Analyst — Architecture & Planning Spec

**Team size:** 4
**Framework:** LangGraph (orchestration) + FastAPI (backend) + Streamlit (frontend)
**LLM provider:** OpenRouter (free-tier models, multi-model fallback)

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

## 5. LangGraph Workflow Diagram

```mermaid
graph TD
    Start([User goal + uploaded files]) --> Supervisor
    Supervisor -->|route: parse docs| DocIngest[Document Ingestion Agent]
    Supervisor -->|route: scanned/image| OCR[Vision/OCR Agent]
    DocIngest --> Supervisor
    OCR --> Supervisor
    Supervisor -->|route: analyze results/enrollment| DataAnalyst[Data Analyst Agent]
    Supervisor -->|route: FB TPE signal| Social[Social Intelligence Agent]
    DataAnalyst --> Supervisor
    Social --> Supervisor
    Supervisor -->|route: semantic lookup needed| RAG[Knowledge/RAG Agent]
    RAG --> Supervisor
    Supervisor -->|all inputs ready| ReportGen[Report Generator Agent]
    ReportGen --> QA[QA/Critic Agent]
    QA -->|issues found| ReportGen
    QA -->|passes checks| HITL{{Human-in-the-Loop\napproval - interrupt()}}
    HITL -->|approved| Finalize([Final report delivered])
    HITL -->|rejected/edit requested| ReportGen
```

The Supervisor is a **hub node**: every worker returns control to it rather than chaining directly to the next agent, which keeps routing logic centralized and lets you add/remove agents without rewiring the graph.

---

## 6. API Specification (FastAPI backend)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/sessions` | Create a session: `{goal, user_id}` → `session_id` |
| `POST` | `/sessions/{id}/documents` | Upload a document (multipart) |
| `POST` | `/sessions/{id}/run` | Kick off the LangGraph run for this session |
| `GET` | `/sessions/{id}` | Session status, current node, plan |
| `WS` | `/sessions/{id}/trace` | Live execution trace stream (node enter/exit, tool calls) |
| `GET` | `/sessions/{id}/messages` | Agent-to-agent communication log |
| `GET` | `/sessions/{id}/graph` | Current graph definition (mermaid/JSON) for the Graph Viewer |
| `GET` | `/sessions/{id}/cost` | Token usage + cost breakdown per agent/model |
| `GET` | `/sessions/{id}/errors` | Structured error log |
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
- **FB Graph API with a CSV/JSON fallback path:** keeps the Social Intelligence Agent demoable even if Meta app review isn't done in time, and keeps you clearly on the compliant side of FB's platform terms.
- **Supervisor as a hub, not a chain:** every agent returns to the Supervisor rather than calling the next agent directly — this keeps the routing logic in one place and makes the system genuinely extensible (adding agent #9 doesn't require touching agent #4's code).

---

## 9. Next Step

Once your team signs off on this doc, implementation starts at **Phase 1** — I'd suggest we build the LangGraph state schema + Supervisor stub and the FastAPI session scaffold first, since everything else (both agent work and UI work) depends on that contract being stable.
