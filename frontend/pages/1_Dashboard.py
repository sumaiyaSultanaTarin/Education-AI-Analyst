"""Upload documents, run intake, and kick off report generation."""

import httpx
import streamlit as st
from utils.api_client import generate_report, get_session, run_intake, upload_document
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header, status_badge

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("📊", "Dashboard", f"Session `{session_id}`")

with st.spinner("Loading session..."):
    record = get_session(session_id)
col_goal, col_status = st.columns([3, 1])
col_goal.markdown(f"**Goal:** {record['goal']}")
col_status.markdown(f"**Status:** {status_badge(record['status'])}", unsafe_allow_html=True)

with st.container(border=True):
    st.subheader("📁 Documents")
    # Keyed on a counter that's bumped after every successful upload — resets
    # the widget to empty afterward, so the same files can't be resubmitted
    # as new documents by clicking Upload again (e.g. a double-click) while
    # they're still sitting in the box.
    uploader_key = f"file_uploader_{st.session_state.get('uploader_version', 0)}"
    uploaded_files = st.file_uploader(
        "Upload documents (PDF, DOCX, PPTX, XLSX, PNG/JPG)",
        accept_multiple_files=True,
        key=uploader_key,
    )
    if uploaded_files and st.button("Upload", type="primary"):
        with st.spinner("Uploading..."):
            for file in uploaded_files:
                try:
                    upload_document(session_id, file.name, file.getvalue(), file.type or "application/octet-stream")
                except httpx.HTTPStatusError as exc:
                    st.error(f"{file.name}: {exc.response.json().get('detail', exc)}")
                else:
                    st.toast(f"Uploaded {file.name}", icon="✅")
        st.session_state["uploader_version"] = st.session_state.get("uploader_version", 0) + 1
        st.rerun()

    if record["documents"]:
        st.table(
            [{"filename": doc["filename"], "type": doc["type"]} for doc in record["documents"]]
        )
    else:
        st.caption("No documents uploaded yet.")

col_intake, col_report = st.columns(2, gap="large")

with col_intake:
    with st.container(border=True):
        st.subheader("⚙️ Run intake")
        st.caption("Extracts text/tables from every uploaded document (Document Ingestion + Vision/OCR agents).")
        if st.button("Run intake", disabled=not record["documents"], use_container_width=True):
            with st.spinner("Running intake..."):
                run_intake(session_id)
            # Rerun so `record` (and the Status pill, and Generate report's
            # disabled state above) reflect the now-updated session instead
            # of the stale copy fetched before this button was clicked.
            st.rerun()

        # Reflects record's *current* state, not just right after a click —
        # same reasoning as the Documents table above: still accurate after
        # navigating back to this page later, not just immediately post-run.
        if record["status"] == "completed":
            if record["errors"]:
                st.warning(f"Intake finished with {len(record['errors'])} error(s) — see Logs/Errors.")
            else:
                st.success("Intake completed with no errors.")
        if record["agent_outputs"]:
            with st.expander("Agent outputs", expanded=False):
                st.json(record["agent_outputs"])

with col_report:
    with st.container(border=True):
        st.subheader("📝 Generate report")
        st.caption("Runs Data Analyst → Knowledge/RAG → Report Generator → QA/Critic, then pauses for HITL approval.")
        if st.button("Generate report", disabled=record["status"] != "completed", type="primary", use_container_width=True):
            with st.spinner("Generating report (this calls an LLM for QA — may take a moment)..."):
                try:
                    status = generate_report(session_id)
                except httpx.HTTPStatusError as exc:
                    st.error(exc.response.json().get("detail", str(exc)))
                else:
                    st.session_state["report_status"] = status
                    st.success(f"Report status: {status['status']} (QA: {status['qa_status']})")
                    st.info("Continue on the HITL Controls page to approve/reject.")
        if record["status"] != "completed":
            st.caption("Run intake first.")
