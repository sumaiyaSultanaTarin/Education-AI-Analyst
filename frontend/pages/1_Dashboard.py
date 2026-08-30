"""Upload documents, run intake, and kick off report generation."""

import httpx
import streamlit as st
from utils.api_client import generate_report, get_session, pull_facebook, run_intake, upload_document
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

with st.container(border=True):
    st.subheader("📘 Facebook (live)")
    st.caption(
        "Pulls real posts/comments from FB_PAGE_ID (.env) via the Graph API — separate "
        "from the CSV-import path above (upload a social_csv file + Run intake)."
    )
    if st.button("Pull Facebook data", use_container_width=True):
        with st.spinner("Calling the Facebook Graph API..."):
            try:
                result = pull_facebook(session_id)
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", str(exc)))
            else:
                if result["errors"]:
                    st.warning(result["errors"][0]["message"])
                else:
                    st.success(f"Pulled {result['posts_found']} post(s) from your Page.")
                    for post in result["posts"]:
                        with st.expander(post["content"][:70] or "(no text)"):
                            for comment in post["comments"]:
                                label = comment["sentiment"]["label"]
                                st.write(f"**[{label}]** {comment['content']}")

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
                except httpx.TimeoutException:
                    st.error(
                        "The backend didn't respond in time. It may still be working in the "
                        "background — wait a bit and reload this page, or try again."
                    )
                except httpx.HTTPStatusError as exc:
                    try:
                        detail = exc.response.json().get("detail", str(exc))
                    except ValueError:
                        # Response body wasn't JSON — e.g. a host/proxy error page
                        # (502/503) returned while the backend was down or restarting,
                        # not an error from our own API.
                        detail = f"Backend returned {exc.response.status_code}: {exc.response.text[:300] or str(exc)}"
                    st.error(detail)
                else:
                    st.session_state["report_status"] = status
                    st.success(f"Report status: {status['status']} (QA: {status['qa_status']})")
                    st.info("Continue on the HITL Controls page to approve/reject.")
        if record["status"] in ("awaiting_approval", "report_ready"):
            st.caption("A report already exists for this session — see HITL Controls / Final Report.")
        elif record["status"] != "completed":
            st.caption("Run intake first.")
