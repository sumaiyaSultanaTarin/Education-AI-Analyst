"""Thin HTTP wrapper around the FastAPI backend (backend/api/).

One function per endpoint that actually exists today — see CLAUDE.md and
docs/architecture.md for the ones that still don't (WS trace, /cost): those
panels (Execution Trace, Token/Cost Tracker) aren't built until that backend
work lands. /messages and /graph now exist (routes/messages.py,
routes/graph_viewer.py).
"""

import os

import httpx

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
_TIMEOUT = 120.0  # generate-report runs embeddings + an LLM call synchronously


def create_session(goal: str, user_id: str) -> dict:
    response = httpx.post(f"{BASE_URL}/sessions", json={"goal": goal, "user_id": user_id}, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_session(session_id: str) -> dict:
    response = httpx.get(f"{BASE_URL}/sessions/{session_id}", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def upload_document(session_id: str, filename: str, file_bytes: bytes, content_type: str) -> dict:
    response = httpx.post(
        f"{BASE_URL}/sessions/{session_id}/documents",
        files={"file": (filename, file_bytes, content_type)},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def run_intake(session_id: str) -> dict:
    response = httpx.post(f"{BASE_URL}/sessions/{session_id}/run", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def generate_report(session_id: str) -> dict:
    response = httpx.post(f"{BASE_URL}/sessions/{session_id}/generate-report", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def hitl_action(session_id: str, node: str, action: str, comment: str | None = None) -> dict:
    """action is one of 'approve', 'reject', 'retry' — matches the route names."""
    payload = {"comment": comment} if action == "reject" else None
    response = httpx.post(
        f"{BASE_URL}/sessions/{session_id}/hitl/{node}/{action}", json=payload, timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def get_report_file(session_id: str, format: str = "docx") -> tuple[bytes, str]:
    """Returns (content, filename). Raises httpx.HTTPStatusError (404) if the
    report isn't generated yet or hasn't been HITL-approved. format is
    'docx' or 'pptx'."""
    response = httpx.get(
        f"{BASE_URL}/sessions/{session_id}/report", params={"format": format}, timeout=_TIMEOUT
    )
    response.raise_for_status()
    default_name = f"report.{format}"
    filename = response.headers.get("content-disposition", "").split("filename=")[-1].strip('"') or default_name
    return response.content, filename


def query_memory(session_id: str, query: str) -> list[dict]:
    response = httpx.get(
        f"{BASE_URL}/sessions/{session_id}/memory", params={"query": query}, timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def get_messages(session_id: str) -> list[dict]:
    response = httpx.get(f"{BASE_URL}/sessions/{session_id}/messages", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_graph_definition(session_id: str) -> dict:
    response = httpx.get(f"{BASE_URL}/sessions/{session_id}/graph", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()
