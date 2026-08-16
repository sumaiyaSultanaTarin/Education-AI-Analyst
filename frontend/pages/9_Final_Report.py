"""Download the approved report."""

import httpx
import streamlit as st
from utils.api_client import get_report_file
from utils.session_state import require_session_id

st.set_page_config(page_title="Final Report", page_icon="📄")
session_id = require_session_id()
st.title("Final Report")

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

_MIME_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

st.success("Report approved and ready.")
for fmt, label in (("docx", "Download report (DOCX)"), ("pptx", "Download report (PPTX)")):
    try:
        content, filename = get_report_file(session_id, format=fmt)
    except httpx.HTTPStatusError as exc:
        st.error(f"{fmt.upper()}: {exc.response.json().get('detail', str(exc))}")
    else:
        st.download_button(label, data=content, file_name=filename, mime=_MIME_TYPES[fmt])
