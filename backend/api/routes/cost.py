"""`/sessions/{id}/cost` — token usage + cost breakdown per agent/model.

Backs the Token/Cost Tracker frontend panel. state["token_usage"] is
populated by core/cost_tracker.record_usage(), called from every agent that
makes an LLM call (agents/qa_critic_agent.py, agents/vision_ocr_agent.py) —
see core/llm_client.py's get_last_usage() for where the numbers come from.

cost_usd is currently always 0.0: every model in the OpenRouter fallback
lists (core/config.py) is a ":free" tier model, and real per-token pricing
for paid models isn't wired up yet.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.session_store import sessions

router = APIRouter(prefix="/sessions", tags=["cost"])


class TokenCostResponse(BaseModel):
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class CostBreakdownResponse(BaseModel):
    by_agent_model: dict[str, TokenCostResponse]
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float


@router.get("/{session_id}/cost", response_model=CostBreakdownResponse)
def get_cost(session_id: str) -> CostBreakdownResponse:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    usage = record.state["token_usage"]
    return CostBreakdownResponse(
        by_agent_model={key: TokenCostResponse(**value) for key, value in usage.items()},
        total_tokens_in=sum(v["tokens_in"] for v in usage.values()),
        total_tokens_out=sum(v["tokens_out"] for v in usage.values()),
        total_cost_usd=sum(v["cost_usd"] for v in usage.values()),
    )
