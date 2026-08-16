"""Visual of the AI team's wiring — the two LangGraph graphs behind the app.

Backed by GET /sessions/{id}/graph (backend/api/routes/graph_viewer.py),
which returns a static mermaid diagram + node/edge list (the pipeline
topology doesn't vary per session). Streamlit has no built-in mermaid
renderer, so the diagram is shown as source you can paste into
https://mermaid.live or any Markdown viewer that supports mermaid fences —
the node/edge table below is the always-visible fallback view.
"""

import streamlit as st
from utils.api_client import get_graph_definition
from utils.session_state import require_session_id

st.set_page_config(page_title="Graph Viewer", page_icon="🕸️")
session_id = require_session_id()
st.title("Graph Viewer")

definition = get_graph_definition(session_id)

st.subheader("Diagram source")
st.caption("Paste this into mermaid.live (or a Markdown viewer with mermaid support) to render it.")
st.code(definition["mermaid"], language="text")

st.subheader("Nodes")
st.table(definition["nodes"])

st.subheader("Edges")
st.table(definition["edges"])
