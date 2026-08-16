"""Shared guard used by every page except Home.py."""

import streamlit as st


def require_session_id() -> str:
    session_id = st.session_state.get("session_id")
    if not session_id:
        st.warning("No active session. Go to Home to create or resume one.")
        st.stop()
    return session_id
