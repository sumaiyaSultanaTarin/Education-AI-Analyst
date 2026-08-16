"""Token usage and cost breakdown per agent/model for this session.

Backed by GET /sessions/{id}/cost (backend/api/routes/cost.py). cost_usd is
currently always $0.00 — every model in the OpenRouter fallback lists is a
":free" tier model (backend/core/config.py), so there's no real per-token
pricing to compute yet. Token counts are real, taken from each LLM
response's usage field (backend/core/llm_client.py).
"""

import streamlit as st
from utils.api_client import get_cost
from utils.session_state import require_session_id

st.set_page_config(page_title="Token / Cost Tracker", page_icon="💰")
session_id = require_session_id()
st.title("Token / Cost Tracker")
st.caption("cost_usd is $0.00 while every model in use is an OpenRouter free-tier model.")

if st.button("Refresh"):
    st.rerun()

breakdown = get_cost(session_id)

col1, col2, col3 = st.columns(3)
col1.metric("Total tokens in", breakdown["total_tokens_in"])
col2.metric("Total tokens out", breakdown["total_tokens_out"])
col3.metric("Total cost", f"${breakdown['total_cost_usd']:.4f}")

st.subheader("By agent / model")
if not breakdown["by_agent_model"]:
    st.info("No LLM calls recorded yet — run intake (for scanned images) or generate a report.")
else:
    rows = [
        {"agent:model": key, **values} for key, values in breakdown["by_agent_model"].items()
    ]
    st.table(rows)
