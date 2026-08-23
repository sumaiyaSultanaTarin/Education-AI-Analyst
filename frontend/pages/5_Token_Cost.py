"""Token usage and API cost estimation — GET /sessions/{id}/cost.

Only QACriticAgent and VisionOCRAgent call an LLM (see AnalystState.token_usage
and core/llm_client.py's last_usage tracking) — the other five agents are
local/deterministic (pandas, sentence-transformers embeddings, a lexicon
sentiment scorer, docx templating), so sessions with no images and no report
generated yet will show all zeros here, correctly.
"""

import streamlit as st
from utils.api_client import get_cost
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Token / Cost Tracker", page_icon="💰", layout="wide")
inject_base_styles()
session_id = require_session_id()

col_title, col_refresh = st.columns([5, 1])
with col_title:
    page_header("💰", "Token Usage & Cost")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

with st.spinner("Loading cost data..."):
    cost = get_cost(session_id)

col1, col2, col3 = st.columns(3)
col1.metric("Tokens in", cost["total_tokens_in"])
col2.metric("Tokens out", cost["total_tokens_out"])
col3.metric("Estimated cost (USD)", f"${cost['total_cost_usd']:.4f}")

if cost["total_cost_usd"] == 0 and (cost["total_tokens_in"] or cost["total_tokens_out"]):
    st.caption(
        "$0.00 is expected here — every OpenRouter fallback model configured for this "
        "project is a free-tier (\":free\") model. Token counts above are still real."
    )

st.subheader("Per-call breakdown")
if not cost["token_usage"]:
    st.caption("No LLM calls recorded yet — these only happen during OCR (image documents) or QA review (Generate report).")
else:
    with st.container(border=True):
        st.table(
            [
                {
                    "call": key,
                    "model": v["model"],
                    "tokens_in": v["tokens_in"],
                    "tokens_out": v["tokens_out"],
                    "cost_usd": v["cost_usd"],
                }
                for key, v in cost["token_usage"].items()
            ]
        )
