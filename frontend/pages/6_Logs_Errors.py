"""Structured error log for this session.

There's no dedicated GET /sessions/{id}/errors endpoint yet — errors are
part of the SessionResponse (backend/api/routes/sessions.py) already
returned by GET /sessions/{id}, so this reuses that instead of adding one.
"""

import streamlit as st
from utils.api_client import get_session
from utils.session_state import require_session_id

st.set_page_config(page_title="Logs / Errors", page_icon="🚨")
session_id = require_session_id()
st.title("Logs / Errors")

record = get_session(session_id)
errors = record["errors"]

report_status = st.session_state.get("report_status")
if report_status and report_status["errors"]:
    errors = errors + [e for e in report_status["errors"] if e not in errors]

if not errors:
    st.success("No errors recorded for this session.")
else:
    st.error(f"{len(errors)} error(s)")
    st.table(errors)
