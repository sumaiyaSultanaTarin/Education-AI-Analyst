"""Download the approved report."""

import httpx
import streamlit as st
from utils.api_client import get_report_file, get_report_status
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Final Report", page_icon="📄", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("📄", "Final Report")

# Fetched fresh on every load (read-only, no graph re-invoke) instead of
# read from st.session_state — that cache is wiped by a browser refresh
# (new WebSocket connection), which used to strand this page on "No report
# generated yet" even for an already-approved report.
try:
    with st.spinner("Loading report status..."):
        status = get_report_status(session_id)
except httpx.HTTPStatusError as exc:
    st.error(exc.response.json().get("detail", str(exc)))
    st.stop()

if status["status"] not in ("awaiting_approval", "report_ready"):
    st.warning("No report generated yet for this session. Generate one from the Dashboard first.")
    st.stop()

if status["status"] != "report_ready":
    st.info(
        f"Report is `{status['status']}` — it must be approved on the HITL Controls page "
        "before it can be downloaded."
    )
    st.stop()

try:
    with st.spinner("Loading report..."):
        content, filename = get_report_file(session_id)
except httpx.HTTPStatusError as exc:
    st.error(exc.response.json().get("detail", str(exc)))
else:
    with st.container(border=True):
        st.success("✅ Report approved and ready.")
        col_download, col_new = st.columns([2, 1])
        with col_download:
            # download_button returns True on the rerun right after it's
            # clicked (same as st.button) — the earliest server-side signal
            # Streamlit gets for a download, since the browser's save step
            # itself happens client-side and isn't reported back to the server.
            downloaded = st.download_button(
                "⬇️ Download report",
                data=content,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )
            if downloaded:
                st.toast(f"Downloaded {filename}", icon="⬇️")
        with col_new:
            if st.button("🏠 Start a new session", use_container_width=True):
                st.session_state.pop("session_id", None)
                st.session_state.pop("report_status", None)
                st.query_params.pop("session", None)
                st.switch_page("Home.py")
