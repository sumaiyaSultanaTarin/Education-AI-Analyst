"""Agent-to-agent communication log — the same GET /sessions/{id}/messages
data as Execution Trace, but framed as a filterable table (from/to/content/
timestamp) rather than a narrative timeline.
"""

import streamlit as st
from utils.api_client import get_messages
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Communication Log", page_icon="💬", layout="wide")
inject_base_styles()
session_id = require_session_id()

col_title, col_refresh = st.columns([5, 1])
with col_title:
    page_header("💬", "Agent Communication Log")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

with st.spinner("Loading messages..."):
    messages = get_messages(session_id)
if not messages:
    st.caption("No messages yet — upload documents and run intake from the Dashboard.")
    st.stop()

agents = sorted({m["from_agent"] for m in messages})
selected = st.multiselect("Filter by sender", agents, default=agents)

filtered = [m for m in messages if m["from_agent"] in selected]
with st.container(border=True):
    st.table(
        [
            {
                "from": m["from_agent"],
                "to": m["to_agent"],
                "content": m["content"],
                "timestamp": m["timestamp"],
            }
            for m in filtered
        ]
    )
st.caption(f"{len(filtered)} of {len(messages)} message(s) shown.")
