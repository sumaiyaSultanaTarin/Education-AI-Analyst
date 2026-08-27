"""Shared guard used by every page except Home.py."""

import httpx
import streamlit as st
from utils.api_client import get_session


def require_session_id() -> str:
    session_id = st.session_state.get("session_id")
    if session_id:
        # Streamlit doesn't carry query params across sidebar page
        # navigation on its own, so every page has to re-assert this on
        # each render — not just Home.py — or a refresh on, say, Dashboard
        # (no ?session in that page's own URL yet) would still lose it.
        st.query_params["session"] = session_id
        return session_id

    # st.session_state lives on the WebSocket connection, so a full page
    # reload (not just a Streamlit rerun) opens a fresh connection and wipes
    # it — even though the session itself is still safe on the backend
    # (data/sessions.db). The URL survives a reload, so fall back to that
    # before giving up.
    from_url = st.query_params.get("session")
    if from_url:
        try:
            get_session(from_url)
        except httpx.HTTPStatusError:
            pass
        else:
            st.session_state["session_id"] = from_url
            return from_url

    st.warning("No active session. Go to Home to create or resume one.")
    st.stop()
