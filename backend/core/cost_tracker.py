"""Folds LLMClient.get_last_usage() into AnalystState.token_usage.

Named/located per docs/architecture.md's folder structure (backend/core/
cost_tracker.py). Keyed by "agent_name:model" — a report run can call the
same agent+model combo more than once (e.g. QA/Critic retries), so repeat
calls accumulate rather than overwrite.
"""

from graph.state import AnalystState, TokenCost


def record_usage(state: AnalystState, agent_name: str, usage: TokenCost | None) -> None:
    """No-op if usage is None (e.g. the LLM call failed before producing a response)."""
    if usage is None:
        return

    key = f"{agent_name}:{usage['model']}"
    existing = state["token_usage"].get(key)
    if existing is None:
        state["token_usage"][key] = dict(usage)
        return

    state["token_usage"][key] = {
        "model": usage["model"],
        "tokens_in": existing["tokens_in"] + usage["tokens_in"],
        "tokens_out": existing["tokens_out"] + usage["tokens_out"],
        "cost_usd": existing["cost_usd"] + usage["cost_usd"],
    }
