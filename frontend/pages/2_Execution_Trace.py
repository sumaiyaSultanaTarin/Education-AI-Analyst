"""Live-ish agent execution trace: the session's plan plus a chronological
timeline of what each agent did.

Not a real push-based WS trace (see utils/api_client.py's docstring) — this
polls GET /sessions/{id}/messages and re-renders as a timeline, since the
graphs run synchronously to completion within one request and there's no
incremental "node entered/exited" event to subscribe to yet. The "Refresh"
button is the practical equivalent of "live" for this MVP.
"""

import streamlit as st
from utils.api_client import get_messages, get_session
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

_AGENT_ICONS = {
    "supervisor": "🧭",
    "document_ingestion": "📄",
    "vision_ocr": "🖼️",
    "social_intelligence": "💬",
    "data_analyst": "📈",
    "knowledge_rag": "🧠",
    "report_generator": "📝",
    "qa_critic": "✅",
    "human": "🧑",
}

st.set_page_config(page_title="Execution Trace", page_icon="🧭", layout="wide")
inject_base_styles()
session_id = require_session_id()

col_title, col_refresh = st.columns([5, 1])
with col_title:
    page_header("🧭", "Live Agent Execution Trace")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

with st.spinner("Loading trace..."):
    record = get_session(session_id)
    messages = get_messages(session_id)
st.markdown(f"**Status:** {record['status']}")

with st.container(border=True):
    st.subheader("Plan")
    if record["plan"]:
        st.table(
            [
                {"step": s["step_id"], "agent": s["agent"], "description": s["description"], "status": s["status"]}
                for s in record["plan"]
            ]
        )
    else:
        st.caption("No plan yet.")

st.subheader("Timeline")
if not messages:
    st.caption("No agent activity yet — upload documents and run intake from the Dashboard.")
else:
    with st.container(border=True):
        for i, msg in enumerate(messages):
            icon = _AGENT_ICONS.get(msg["from_agent"], "🤖")
            st.markdown(f"{icon} **{msg['from_agent']}** → `{msg['to_agent']}`  \n{msg['content']}")
            st.caption(msg["timestamp"])
            if i < len(messages) - 1:
                st.divider()
