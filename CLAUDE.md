# CLAUDE.md

This file is read automatically by Claude Code whenever anyone opens a terminal in this repo.
Keep it accurate — it's how all 4 teammates get consistent behavior from Claude Code instead of
each person's AI making different assumptions about the project.

## What this project is

A multi-agent AI system (Supervisor + 7 worker agents) that analyzes education documents
(PDF/DOCX/PPTX/XLSX/images), pulls Facebook comments for teacher-performance signals, and
produces an approved report. Full plan: `docs/spec-simple.md` (plain language) and
`docs/architecture.md` (technical detail, ERD, API spec, roadmap).

## Stack

- Orchestration: LangGraph
- LLMs: OpenRouter (free-tier models, with a fallback list — never assume one model is always available)
- Backend: FastAPI (`backend/`)
- Frontend: Streamlit (`frontend/`)
- Vector memory: Chroma (`data/chroma_db/`, one collection per data type — don't mix document
  chunks and social-media chunks in the same collection)
- Structured data: Postgres in production, SQLite for local dev (`backend/db/`)
- Embeddings: local `sentence-transformers`, NOT an API (OpenRouter doesn't serve embeddings)

## Folder ownership (who's building what)

- `backend/agents/`, `backend/tools/` — Person C (domain agents)
- `backend/graph/`, HITL/interrupt logic — Person B (agent/graph wiring)
- `backend/api/`, `backend/db/`, `backend/core/` — Person A (backend/infra)
- `frontend/` — Person D (UI)

Check with the owning teammate before making structural changes outside your own lane —
small fixes are fine, but don't silently redesign someone else's agent or API contract.

## Conventions

- Every agent lives in its own file in `backend/agents/`, one class, and only talks to the
  Supervisor — agents never call each other directly.
- Every LLM call goes through `backend/core/llm_client.py` (handles the OpenRouter fallback
  list and retry/backoff) — never call OpenRouter directly from an agent file.
- Every tool function needs a docstring and at least one test in `backend/tests/`.
- Log through `backend/core/logging_config.py`, not bare `print()`.
- New API endpoints go in `backend/api/routes/`, one file per resource, and must be added to
  `docs/architecture.md`'s API table in the same PR.

## Commands

- Backend: `cd backend && uvicorn api.main:app --reload`
- Frontend: `cd frontend && streamlit run Home.py`
- Tests: `cd backend && pytest`

## Do NOT

- Do not commit `.env`, anything in `data/uploads/`, or `data/chroma_db/` — see `.gitignore`.
- Do not hardcode API keys anywhere — use `backend/core/config.py` reading from `.env`.
- Do not scrape Facebook directly — use the official Graph API path in
  `backend/tools/fb_graph_api_tools.py`, or the CSV-import fallback. See `docs/spec-simple.md` §7.
