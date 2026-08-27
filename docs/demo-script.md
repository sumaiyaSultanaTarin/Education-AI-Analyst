# Education AI Analyst — Live Demo Script

For presenting to the supervisor against the assignment rubric. Pairs with the
page-by-page verification checklist the team already validated (same click
order); this version adds *what to say*, not just what to click.

Every step below has been run live end-to-end on a real machine (real
OpenRouter + Tavily keys, real report generated, approved, and downloaded) —
this isn't a "should work" script.

## Before you start

1. `backend/.env` has a real `OPENROUTER_API_KEY` (openrouter.ai, free) — without
   it, QA/Critic and Vision/OCR still run but silently degrade (QA auto-passes,
   OCR logs an error). Optional: `TAVILY_API_KEY` (tavily.com, free) so the
   Data Analyst's web-search context step returns real results instead of a
   logged, non-fatal skip — when it's set, the final report gets an extra
   "External Benchmark Context" section with real external results.
   `OPENROUTER_FALLBACK_MODELS`/`OPENROUTER_VISION_FALLBACK_MODELS` in
   `.env`/`.env.example` were verified against real calls on 2026-08-27 —
   free-tier availability rotates, so re-check openrouter.ai/models if a
   model starts erroring out closer to the actual demo.
2. `cd backend && uvicorn api.main:app --reload` — confirm `http://localhost:8000/health`.
3. `cd frontend && streamlit run Home.py`.
4. Have 2–3 files from `data/sample_docs/` ready (one PDF/DOCX/XLSX + one PNG).

## Opening (30 seconds)

"This is a multi-agent system — a Supervisor coordinating seven specialized
agents — that turns raw education documents and Facebook comments into an
approved report, with a human sign-off gate before anything is finalized."

## Walkthrough (~8 minutes)

| # | Page | Click | Say |
|---|---|---|---|
| 1 | Home | Enter a goal, create session | "Every other panel reads from this one session ID." |
| 2 | Dashboard | Upload 2–3 files → Run intake → Generate report | "Intake fans out by file type to Document Ingestion or Vision/OCR. Generate report chains Data Analyst → Knowledge/RAG → Report Generator → QA/Critic, then pauses for a human." |
| 3 | Execution Trace | — | "One entry per real agent action, in the order they actually ran — not scripted." |
| 4 | Communication Log | Filter to one agent | "Same data as the trace, framed as agent-to-agent messages — this is how the Supervisor-hub pattern stays observable instead of being a black box." |
| 5 | Execution Graph | Flip both tabs | **Say this explicitly** — graders won't notice otherwise: "This isn't a hand-drawn diagram. It's `.get_graph().draw_mermaid()` called on the actual compiled LangGraph objects, so it's structurally impossible for this diagram to drift from the real code." |
| 6 | Token / Cost | — | "$0.00 is correct, not broken — every fallback model is free-tier. The per-call breakdown above it is real token data from the actual API responses." |
| 7 | Logs / Errors | — | "Every failure — a bad file, a missing key, a rate limit — becomes a structured error record here instead of crashing the run." |
| 8 | Memory Viewer | Run one query | "Semantic search over Chroma — this is genuine RAG, not keyword matching." |
| 9 | HITL Controls | Reject once with a comment, then Approve (or Retry) | "Reject/Retry both loop back to Report Generator — the graph is genuinely paused via LangGraph's `interrupt()`, checkpointed to disk, not just a UI flag. It survives a backend restart." |
| 10 | Final Report | Download | "Approval is enforced server-side — hitting the download URL directly before approval still 404s. And notice the address bar has `?session=...` in it — refreshing the browser mid-demo won't lose anything." |

## Points worth stating out loud (easy to miss just by clicking)

- **Supervisor-as-hub, not peer-to-peer.** Agents only talk to the Supervisor,
  never each other directly (`CLAUDE.md` convention) — a deliberate choice,
  documented in `docs/architecture.md`, not a missing feature.
- **Two separate compiled graphs, not one.** Document intake (loops until every
  file is processed) and analysis/report/HITL (linear with a checkpointed
  pause) are built and compiled independently — see `graph/graph_builder.py`
  vs `graph/report_graph_builder.py`.
- **Sessions survive a restart, or an accidental refresh.** Both the session
  state and the paused HITL checkpoint are persisted to SQLite
  (`data/sessions.db`, `data/checkpoints.db`) — a session paused mid-approval
  isn't lost if the backend restarts. Separately, the session ID also lives
  in the browser URL (`?session=...`), so a frontend page refresh — the kind
  that's easy to trigger by accident mid-demo — doesn't lose it either.
- **Real external data lands in the actual deliverable.** The Data Analyst's
  web-search step (Tavily) isn't just computed and discarded — its results
  show up as an "External Benchmark Context" section in the downloaded
  report itself, cited with real URLs.
- **Two Facebook input paths, same downstream code.** CSV import (always
  available, used for the demo) and a real Graph API path
  (`tools/fb_graph_api_tools.py`, works against any Page you admin, no Meta
  App Review needed) both feed the same sentiment-scoring step.
- **Free-tier LLM fallback, not a single point of failure.** Every LLM call
  tries a list of free OpenRouter models in order (`core/llm_client.py`) —
  say this if a model is visibly rate-limited during the live demo.

## If something breaks live

- **A model is rate-limited / OCR or QA errors out:** point at Logs/Errors —
  "this is the fallback-list retry logic surfacing a real failure, not a
  crash" — then move on; the run still completes.
- **Embedding model download is slow on first run:** `sentence-transformers`
  downloads `all-MiniLM-L6-v2` (~90MB) on first use and caches it — run
  Generate report once *before* presenting so this isn't live-demoed.
- **Web search shows no results:** expected without `TAVILY_API_KEY` set —
  logged as a skip, not a failure; mention it's optional context, not core
  to the report.
- **You accidentally refresh the browser:** it should just work now — the
  session ID lives in the URL, and the page restores itself. If it somehow
  doesn't (e.g. you navigated away and the URL lost the `?session=...`
  part), copy the session ID from Home's "Resume an existing session" form.
- **`.env` was just edited (a new key, a model swapped):** the backend only
  auto-reloads on `.py` file changes, not `.env` — restart it manually
  (Ctrl+C, then `uvicorn api.main:app --reload` again) or the change won't
  take effect.
