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
uploaded_files = st.file_uploader(
    "Upload documents (PDF, DOCX, PPTX, XLSX, PNG/JPG)", accept_multiple_files=True
)
if uploaded_files and st.button("Upload"):
    for file in uploaded_files:
        try:
            upload_document(session_id, file.name, file.getvalue(), file.type or "application/octet-stream")
        except httpx.HTTPStatusError as exc:
            st.error(f"{file.name}: {exc.response.json().get('detail', exc)}")
        else:
            st.success(f"Uploaded {file.name}")
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
        result = run_intake(session_id)
    if result["errors"]:
        st.warning(f"Intake finished with {len(result['errors'])} error(s) — see Logs/Errors.")
    else:
        st.success("Intake completed with no errors.")
    st.json(result["agent_outputs"], expanded=False)

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
if record["status"] != "completed":
    st.caption("Run intake first.")
