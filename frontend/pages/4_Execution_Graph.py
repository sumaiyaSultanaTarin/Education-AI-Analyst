"""LangGraph structure viewer — renders the mermaid source GET
/sessions/{id}/graph returns for both compiled graphs (intake, and the
analysis/report/HITL graph) via mermaid.js loaded from a CDN.

The graph *structure* is static (every session runs the same two compiled
graphs) — this doesn't highlight which node is currently active, since the
graphs run synchronously to completion and there's no live position to show
(see Execution Trace for what actually happened, after the fact).
"""

import streamlit.components.v1 as components
import streamlit as st
from utils.api_client import get_graph
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Execution Graph", page_icon="🕸️", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("🕸️", "Execution Graph", "Structure of both compiled LangGraph pipelines")


def _render_mermaid(source: str, height: int = 440) -> None:
    # preconnect hints the browser to open the CDN connection immediately
    # instead of waiting for the parser to reach the <script> tag below.
    components.html(
        f"""
        <link rel="preconnect" href="https://cdn.jsdelivr.net">
        <style>
            body {{ font-family: "Source Sans Pro", sans-serif; }}
            .mermaid {{ display: flex; justify-content: center; }}
        </style>
        <div class="mermaid">{source}</div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                theme: "base",
                themeVariables: {{ primaryColor: "#EEF2FF", primaryBorderColor: "#4F46E5", lineColor: "#818CF8" }},
            }});
        </script>
        """,
        height=height,
        scrolling=True,
    )


with st.spinner("Loading graph..."):
    graphs = get_graph(session_id)

tab_intake, tab_report = st.tabs(["📄 Document Intake", "📝 Analysis / Report / HITL"])
with tab_intake:
    with st.container(border=True):
        st.caption("supervisor routes each document to the worker agent matching its type, then loops.")
        _render_mermaid(graphs["intake"])
with tab_report:
    with st.container(border=True):
        st.caption("data_analyst → knowledge_rag → report_generator → qa_critic → hitl_approval, looping on fail/reject.")
        _render_mermaid(graphs["report"])
