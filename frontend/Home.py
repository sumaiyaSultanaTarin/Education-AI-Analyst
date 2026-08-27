"""Landing page — create a new analysis session or resume an existing one.

Every other page reads st.session_state["session_id"], so this is the one
place that sets it.
"""

import httpx
import streamlit as st
from utils.api_client import BASE_URL, create_session, get_session

st.set_page_config(page_title="Education AI Analyst", page_icon="🎓")
st.title("Education AI Analyst")
st.caption(f"Backend: {BASE_URL}")

try:
    httpx.get(f"{BASE_URL}/health", timeout=5.0).raise_for_status()
except httpx.HTTPError:
    st.error(
        "Can't reach the backend. Start it with `cd backend && uvicorn api.main:app --reload` "
        "and refresh this page."
    )
    st.stop()

active_id = st.session_state.get("session_id")
if not active_id:
    # A full page reload (not just a Streamlit rerun) opens a fresh
    # WebSocket connection and wipes st.session_state — the URL survives
    # that, so restore from ?session=<id> before treating this as a
    # brand-new visitor. The session itself was never actually lost; it's
    # been sitting in data/sessions.db the whole time.
    from_url = st.query_params.get("session")
    if from_url:
        try:
            get_session(from_url)
        except httpx.HTTPStatusError:
            pass
        else:
            active_id = from_url
            st.session_state["session_id"] = from_url

if active_id:
    st.query_params["session"] = active_id
    st.success(f"Active session: `{active_id}`")
    if st.button("Start a new session instead"):
        st.session_state.pop("session_id", None)
        st.session_state.pop("report_status", None)
        st.query_params.pop("session", None)
        st.rerun()

st.subheader("Create a new session")
with st.form("create_session"):
    goal = st.text_area("Goal", placeholder="Summarize this term's enrollment and results")
    user_id = st.text_input("User ID", value="demo-user")
    submitted = st.form_submit_button("Create session")

if submitted:
    if not goal.strip():
        st.error("Goal can't be empty.")
    else:
        record = create_session(goal, user_id)
        st.session_state["session_id"] = record["session_id"]
        st.session_state["report_status"] = None
        st.query_params["session"] = record["session_id"]
        st.success(f"Created session `{record['session_id']}`. Head to Dashboard to upload documents.")
        st.rerun()

st.subheader("Resume an existing session")
with st.form("resume_session"):
    existing_id = st.text_input("Session ID")
    resumed = st.form_submit_button("Resume")

if resumed:
    if not existing_id.strip():
        st.error("Session ID can't be empty.")
    else:
        try:
            get_session(existing_id)
        except httpx.HTTPStatusError:
            st.error("No session found with that ID.")
        else:
            st.session_state["session_id"] = existing_id
            st.session_state["report_status"] = None
            st.query_params["session"] = existing_id
            st.success(f"Resumed session `{existing_id}`.")
            st.rerun()
