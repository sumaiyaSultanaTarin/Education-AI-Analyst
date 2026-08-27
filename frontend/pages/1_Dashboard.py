"""Upload documents, run intake, and kick off report generation."""

import httpx
import streamlit as st
from utils.api_client import generate_report, get_session, run_intake, upload_document
from utils.session_state import require_session_id

st.set_page_config(page_title="Dashboard", page_icon="📊")
session_id = require_session_id()
st.title("Dashboard")

record = get_session(session_id)
st.write(f"**Goal:** {record['goal']}")
st.write(f"**Status:** {record['status']}")

st.subheader("Documents")
# Keyed on a counter that's bumped after every successful upload — resets
# the widget to empty afterward, so the same files can't be resubmitted as
# new documents by clicking Upload again (e.g. a double-click) while
# they're still sitting in the box.
uploader_key = f"file_uploader_{st.session_state.get('uploader_version', 0)}"
uploaded_files = st.file_uploader(
    "Upload documents (PDF, DOCX, PPTX, XLSX, PNG/JPG)",
    accept_multiple_files=True,
    key=uploader_key,
)
if uploaded_files and st.button("Upload"):
    for file in uploaded_files:
        try:
            upload_document(session_id, file.name, file.getvalue(), file.type or "application/octet-stream")
        except httpx.HTTPStatusError as exc:
            st.error(f"{file.name}: {exc.response.json().get('detail', exc)}")
        else:
            st.success(f"Uploaded {file.name}")
    st.session_state["uploader_version"] = st.session_state.get("uploader_version", 0) + 1
    st.rerun()

if record["documents"]:
    st.table(
        [{"filename": doc["filename"], "type": doc["type"]} for doc in record["documents"]]
    )
else:
    st.caption("No documents uploaded yet.")

st.subheader("Run intake")
st.caption("Extracts text/tables from every uploaded document (Document Ingestion + Vision/OCR agents).")
if st.button("Run intake", disabled=not record["documents"]):
    with st.spinner("Running intake..."):
        run_intake(session_id)
    # Rerun so `record` (and Generate report's disabled state below) reflect
    # the now-updated session instead of the stale copy fetched before this
    # button was clicked.
    st.rerun()

if record["status"] == "completed":
    if record["errors"]:
        st.warning(f"Intake finished with {len(record['errors'])} error(s) — see Logs/Errors.")
    else:
        st.success("Intake completed with no errors.")
if record["agent_outputs"]:
    st.json(record["agent_outputs"], expanded=False)

st.subheader("Generate report")
st.caption("Runs Data Analyst → Knowledge/RAG → Report Generator → QA/Critic, then pauses for HITL approval.")
if st.button("Generate report", disabled=record["status"] != "completed"):
    with st.spinner("Generating report (this calls an LLM for QA — may take a moment)..."):
        try:
            status = generate_report(session_id)
        except httpx.HTTPStatusError as exc:
            st.error(exc.response.json().get("detail", str(exc)))
        else:
            st.session_state["report_status"] = status
            st.success(f"Report status: {status['status']} (QA: {status['qa_status']})")
            st.info("Continue on the HITL Controls page to approve/reject.")
if record["status"] in ("awaiting_approval", "report_ready"):
    st.caption("A report already exists for this session — see HITL Controls / Final Report.")
elif record["status"] != "completed":
    st.caption("Run intake first.")
