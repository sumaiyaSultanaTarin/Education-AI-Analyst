"""`/sessions/{id}/messages`, `/sessions/{id}/graph`, `/sessions/{id}/cost` —
the panels docs/architecture.md's API table calls the Communication Log,
Graph Viewer, and Token/Cost Tracker (see that table's WS/messages/graph/cost
rows).

The WS `/sessions/{id}/trace` row in that table (a live, node-enter/exit push
stream) is NOT implemented here — the intake/report graphs run synchronously
to completion inside a single request (see graph_builder.py, report_pipeline.py)
and don't emit incremental events, so there's nothing to stream yet. Every
route below is a plain polled GET reading data agents already record into
AnalystState as they run (state["messages"], state["token_usage"]) plus the
static compiled-graph structure, which the frontend polls after each action
instead of subscribing to a socket.
"""

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from api import report_pipeline
from api.session_store import sessions
from graph.graph_builder import build_graph

router = APIRouter(prefix="/sessions", tags=["observability"])


@lru_cache(maxsize=1)
def _intake_graph():
    return build_graph()


def _get_record_or_404(session_id: str):
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.get("/{session_id}/messages")
def get_messages(session_id: str) -> list[dict]:
    """Agent-to-agent communication log, in the order agents ran.

    Every agent appends one AgentMessage to state["messages"] when it
    finishes (see e.g. agents/document_ingestion_agent.py) — this just
    returns that list, which already covers both the intake graph and the
    later analysis/report/HITL graph since both share the same session state.
    """
    record = _get_record_or_404(session_id)
    return list(record.state["messages"])


@router.get("/{session_id}/graph")
def get_graph(session_id: str) -> dict[str, str]:
    """Mermaid source for both compiled graphs, for the Graph Viewer panel.

    The graph *structure* is static and identical for every session — this
    is session-scoped (per docs/architecture.md) only so a request for an
    unknown session still 404s like the other endpoints here, rather than
    silently succeeding.
    """
    _get_record_or_404(session_id)
    return {
        "intake": _intake_graph().get_graph().draw_mermaid(),
        "report": report_pipeline.get_report_graph().get_graph().draw_mermaid(),
    }


@router.get("/{session_id}/cost")
def get_cost(session_id: str) -> dict:
    """Token usage + cost estimate per LLM call this session has made.

    Populated by the two agents that actually call an LLM (QACriticAgent,
    VisionOCRAgent) — see AnalystState.token_usage and core/llm_client.py's
    last_usage tracking. Every configured fallback model is free-tier, so
    cost_usd is genuinely $0.00 today; the per-call breakdown is still real
    and is what a paid model would need to show a non-zero total.
    """
    record = _get_record_or_404(session_id)
    usage = dict(record.state["token_usage"])
    return {
        "token_usage": usage,
        "total_tokens_in": sum(u["tokens_in"] for u in usage.values()),
        "total_tokens_out": sum(u["tokens_out"] for u in usage.values()),
        "total_cost_usd": round(sum(u["cost_usd"] for u in usage.values()), 6),
    }
