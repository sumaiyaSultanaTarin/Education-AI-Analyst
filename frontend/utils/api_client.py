"""Thin HTTP wrapper around the FastAPI backend (backend/api/).

One function per endpoint that actually exists today. The WS /sessions/{id}/trace
push stream from docs/architecture.md's API table is still not implemented —
the graphs run synchronously to completion inside one request and don't emit
incremental events (see backend/api/routes/observability.py's docstring) — so
Execution Trace/Communication Log/Graph Viewer/Token-Cost all poll the plain
GET endpoints below instead of subscribing to a socket.
"""

import os

import httpx
import streamlit as st

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
_TIMEOUT = 120.0  # generate-report runs embeddings + an LLM call synchronously

# One pooled connection reused across every call/page/rerun instead of a
# fresh TCP connection per request — every page was paying reconnect
# overhead on its very first call each time it loaded. Module-level (not
# st.cache_resource): the module is only imported once per server process,
# so this already survives every rerun and every page navigation for free.
_client = httpx.Client(base_url=BASE_URL, timeout=_TIMEOUT)


def create_session(goal: str, user_id: str) -> dict:
    response = _client.post("/sessions", json={"goal": goal, "user_id": user_id})
    response.raise_for_status()
    return response.json()


def get_session(session_id: str) -> dict:
    response = _client.get(f"/sessions/{session_id}")
    response.raise_for_status()
    return response.json()


def upload_document(session_id: str, filename: str, file_bytes: bytes, content_type: str) -> dict:
    response = _client.post(
        f"/sessions/{session_id}/documents",
        files={"file": (filename, file_bytes, content_type)},
    )
    response.raise_for_status()
    return response.json()


def run_intake(session_id: str) -> dict:
    response = _client.post(f"/sessions/{session_id}/run")
    response.raise_for_status()
    return response.json()


def generate_report(session_id: str) -> dict:
    response = _client.post(f"/sessions/{session_id}/generate-report")
    response.raise_for_status()
    return response.json()


def get_report_status(session_id: str) -> dict:
    """Read-only — safe to call on every page load to survive a browser
    refresh, unlike generate_report() which re-runs the QA/Critic LLM call."""
    response = _client.get(f"/sessions/{session_id}/report-status")
    response.raise_for_status()
    return response.json()


def hitl_action(session_id: str, node: str, action: str, comment: str | None = None) -> dict:
    """action is one of 'approve', 'reject', 'retry' — matches the route names."""
    payload = {"comment": comment} if action == "reject" else None
    response = _client.post(f"/sessions/{session_id}/hitl/{node}/{action}", json=payload)
    response.raise_for_status()
    return response.json()


def get_report_file(session_id: str) -> tuple[bytes, str]:
    """Returns (content, filename). Raises httpx.HTTPStatusError (404) if the
    report isn't generated yet or hasn't been HITL-approved."""
    response = _client.get(f"/sessions/{session_id}/report")
    response.raise_for_status()
    filename = response.headers.get("content-disposition", "").split("filename=")[-1].strip('"') or "report.docx"
    return response.content, filename


def get_messages(session_id: str) -> list[dict]:
    response = _client.get(f"/sessions/{session_id}/messages")
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def get_graph(session_id: str) -> dict:
    """Returns {"intake": "<mermaid>", "report": "<mermaid>"}.

    Cached: the compiled graph structure never changes for the lifetime of
    the backend process, so re-fetching it on every visit/rerun of the Graph
    Viewer page is pure network overhead. 5 min TTL just bounds staleness if
    the backend is ever restarted with different graph wiring mid-session.
    """
    response = _client.get(f"/sessions/{session_id}/graph")
    response.raise_for_status()
    return response.json()


def get_cost(session_id: str) -> dict:
    response = _client.get(f"/sessions/{session_id}/cost")
    response.raise_for_status()
    return response.json()


def query_memory(session_id: str, query: str) -> list[dict]:
    response = _client.get(f"/sessions/{session_id}/memory", params={"query": query})
    response.raise_for_status()
    return response.json()
