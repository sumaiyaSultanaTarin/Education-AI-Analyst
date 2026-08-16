"""Agent-to-agent communication log for this session.

Backed by GET /sessions/{id}/messages (backend/api/routes/messages.py),
which just exposes state["messages"] — every agent appends there as it runs.
"""

import streamlit as st
from utils.api_client import get_messages
from utils.session_state import require_session_id

st.set_page_config(page_title="Communication Log", page_icon="💬")
session_id = require_session_id()
st.title("Communication Log")
st.caption("Messages agents sent to the Supervisor as they ran.")

if st.button("Refresh"):
    st.rerun()

messages = get_messages(session_id)

if not messages:
    st.info("No messages yet — run intake or generate a report first.")
else:
    for message in messages:
        with st.container(border=True):
            st.caption(f"{message['timestamp']}")
            st.write(f"**{message['from_agent']}** → **{message['to_agent']}**")
            st.write(message["content"])
