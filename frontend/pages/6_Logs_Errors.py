"""Structured error log for this session.

There's no dedicated GET /sessions/{id}/errors endpoint yet — errors are
part of the SessionResponse (backend/api/routes/sessions.py) already
returned by GET /sessions/{id}, so this reuses that instead of adding one.

record["errors"] already includes report/QA-stage errors too, not just
intake errors: api/session_store.py's `sessions` dict is shared by every
route module, and report_pipeline.apply_result() mutates the same
SessionRecord.state in place after a generate-report/hitl call — so this
doesn't need (and previously wrongly relied on) st.session_state["report_status"]
to see those, which was wiped by a browser refresh.
"""

import streamlit as st
from utils.api_client import get_session
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Logs / Errors", page_icon="🚨", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("🚨", "Logs / Errors")

with st.spinner("Loading logs..."):
    record = get_session(session_id)
errors = record["errors"]

if not errors:
    st.success("No errors recorded for this session.")
else:
    st.error(f"{len(errors)} error(s)")
    with st.container(border=True):
        st.table(errors)
