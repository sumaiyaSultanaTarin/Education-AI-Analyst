# Education AI Analyst — Final Task Assignment

**Team:** Tarin, Saif (coding), Shohana, Fahim (coding + support)
**Branches:** `dev_tarin`, `dev_saif`, `dev_shohana`, `dev_fahim` → merged into `develop`

---

## Team & Branch Overview

| Member | Branch | Role |
|---|---|---|
| Tarin | `dev_tarin` | Core backend, agent pipeline foundation |
| Saif | `dev_saif` | Knowledge, analysis, output generation, UI |
| Shohana | `dev_shohana` | Sample data, social intelligence agent, docs |
| Fahim | `dev_fahim` | Testing, deployment, CI/CD, demo |

---

## Phase 0 — Planning & Architecture ✅ Done

| Task | Owner |
|---|---|
| Requirement analysis, architecture, ERD, API spec, roadmap | All four |

---

## Phase 1 — Foundation

| Task | Owner | Notes |
|---|---|---|
| FastAPI scaffold (`/sessions` endpoints, config, logging) | **Tarin** | |
| LangGraph state schema + Supervisor stub | **Tarin** | |
| `llm_client.py` — OpenRouter free-model fallback list (+ optional Grok fallback) | **Tarin** | |
| Sample/test data pack (synthetic Excel results, PDF, DOCX, test images) | **Shohana** | Runs in parallel — needed before agents can be tested |

---

## Phase 2 — Intake Agents

| Task | Owner |
|---|---|
| Document Ingestion Agent (PDF/DOCX/PPTX/XLSX → text) | **Tarin** |
| Vision/OCR Agent (image/scanned → text) | **Tarin** |

*Depends on: Phase 1 skeleton + sample data.*

---

## Phase 3 — Knowledge & Analysis

| Task | Owner |
|---|---|
| Knowledge/RAG Agent (Chroma embedding + retrieval) | **Saif** |
| Data Analyst Agent (pandas over results/enrollment data) | **Saif** |

*Depends on: Phase 2 (needs ingested text to embed/analyze).*

---

## Phase 4 — Social Intelligence

| Task | Owner |
|---|---|
| Social Intelligence Agent — CSV-import fallback path | **Shohana** |
| 🔴 **HARD TASK:** Full Facebook Graph API integration — OAuth flow, page/group permissions, token refresh, live post/comment retrieval | **Shohana** |

*Can run in parallel with Phase 3.*

---

## Phase 5 — Output Generation

| Task | Owner |
|---|---|
| Report Generator Agent (DOCX/PPTX output with citations) | **Saif** |
| QA/Critic Agent (fact-checks report against source data) | **Saif** |
| HITL wiring — `interrupt()` before final report release | **Saif** |

*Depends on: Phase 3 (needs RAG + analysis outputs to compile).*

---

## Phase 6 — Frontend (Streamlit)

| Task | Owner |
|---|---|
| Dashboard, Execution Trace, Communication Log panels | **Saif** |
| Graph Viewer, Token/Cost Tracker panels | **Saif** |
| Logs/Errors, Memory Viewer panels | **Saif** |
| HITL Controls, Final Report Viewer panels | **Saif** |

*Depends on: Phase 1 API being stable; can start early against mocked responses.*

---

## Phase 7 — Testing

| Task | Owner |
|---|---|
| Unit tests per tool/agent (`backend/tests/`) | **Fahim** |
| FB fallback sample CSV for testing | **Fahim** |
| Integration testing / end-to-end bug bash | **Fahim** |

*Depends on: agents from Phases 2–5 existing.*

---

## Phase 8 — Deployment

| Task | Owner |
|---|---|
| 🔴 **HARD TASK:** Multi-service `docker-compose.yml` (backend + frontend + Postgres + Chroma networked) + GitHub Actions CI pipeline running tests/builds on push to `develop` | **Fahim** |

*Can be scaffolded early, finalized once services are stable.*

---

## Phase 9 — Documentation & Demo Prep

| Task | Owner |
|---|---|
| Keep `docs/architecture.md` and ERD updated as schema evolves | **Shohana** |
| Demo script / presentation slides | **Fahim** |

*Ongoing throughout, finalized at the end.*

---

## Phase 10 — Final Integration & Polish

| Task | Owner |
|---|---|
| Merge all branches into `develop`, resolve conflicts, full run-through | **All four** |

---

## Dependency Flow (summary)

```
Phase 1 (Tarin: skeleton | Shohana: sample data)
   │
   ▼
Phase 2 (Tarin: intake agents)
   │
   ├──▶ Phase 3 (Saif: RAG + data analysis)
   │         │
   │         ▼
   │     Phase 5 (Saif: report + QA + HITL)
   │         │
   └──▶ Phase 4 (Shohana: social intel)   │
             │                            ▼
             └──────────────────▶ Phase 6 (Saif: UI)
                                       │
                                       ▼
                              Phase 7 (Fahim: testing)
                                       │
                                       ▼
                              Phase 8 (Fahim: deployment)
                                       │
                                       ▼
                              Phase 10 (All: final polish)
```

Phase 9 (docs/demo) runs alongside everything, not blocking or blocked by the others.
