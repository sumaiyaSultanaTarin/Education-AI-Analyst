"""Approve, reject, or retry the report paused at the hitl_approval node.

Fetches the current status fresh from GET /sessions/{id}/report-status on
every load rather than trusting st.session_state["report_status"] — that
cache only exists in the browser tab that ran generate-report, and is wiped
by a page refresh (new WebSocket connection). report-status is read-only
(no graph re-invoke), so calling it on every load is cheap and always
correct, including after a refresh or when opened in a second tab.
"""

import httpx
import streamlit as st
from utils.api_client import get_report_status, hitl_action
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header, status_badge

_NODE = "hitl_approval"

st.set_page_config(page_title="HITL Controls", page_icon="🧑‍⚖️", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("🧑‍⚖️", "Human-in-the-Loop Controls")

try:
    with st.spinner("Loading report status..."):
        status = get_report_status(session_id)
except httpx.HTTPStatusError as exc:
    st.error(exc.response.json().get("detail", str(exc)))
    st.stop()

if status["status"] not in ("awaiting_approval", "report_ready"):
    st.warning("No report generated yet for this session. Generate one from the Dashboard first.")
    st.stop()

with st.container(border=True):
    col_status, col_qa = st.columns(2)
    col_status.markdown(f"**Status:** {status_badge(status['status'])}", unsafe_allow_html=True)
    col_qa.markdown(f"**QA verdict:** {status_badge(status['qa_status'])}", unsafe_allow_html=True)
    if status["hitl_status"]:
        st.json(status["hitl_status"])

if status["errors"]:
    st.warning(f"{len(status['errors'])} error(s) — see Logs/Errors.")


def _act(action: str, comment: str | None = None) -> None:
    try:
        hitl_action(session_id, _NODE, action, comment)
    except httpx.HTTPStatusError as exc:
        st.error(exc.response.json().get("detail", str(exc)))
    else:
        # No need to cache the response — the rerun below re-fetches fresh
        # via get_report_status() above.
        st.rerun()


if status["status"] == "report_ready":
    st.success("Already approved — see Final Report.")
elif status["status"] == "awaiting_approval":
    with st.container(border=True):
        col1, col2 = st.columns(2)
        if col1.button("✅ Approve", type="primary", use_container_width=True):
            _act("approve")
        if col2.button("🔁 Retry", use_container_width=True):
            _act("retry")

        with st.form("reject_form"):
            comment = st.text_area("Rejection comment (optional)")
            if st.form_submit_button("❌ Reject", use_container_width=True):
                _act("reject", comment or None)
else:
    st.info(f"Nothing to approve — current status is `{status['status']}`.")
