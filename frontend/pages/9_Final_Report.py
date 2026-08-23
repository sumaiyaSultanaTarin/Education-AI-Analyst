"""Download the approved report."""

import httpx
import streamlit as st
from utils.api_client import get_report_file
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Final Report", page_icon="📄", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("📄", "Final Report")

status = st.session_state.get("report_status")
if status is None:
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
        # download_button returns True on the rerun right after it's clicked
        # (same as st.button) — the earliest server-side signal Streamlit
        # gets for a download, since the browser's save step itself happens
        # client-side and isn't reported back to the server.
        downloaded = st.download_button(
            "⬇️ Download report",
            data=content,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        if downloaded:
            st.toast(f"Downloaded {filename}", icon="⬇️")
