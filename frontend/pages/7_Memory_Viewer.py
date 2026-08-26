"""Query the Chroma vector store for this session's indexed document chunks."""

import httpx
import streamlit as st
from utils.api_client import query_memory
from utils.session_state import require_session_id
from utils.ui import inject_base_styles, page_header

st.set_page_config(page_title="Memory Viewer", page_icon="🧠", layout="wide")
inject_base_styles()
session_id = require_session_id()
page_header("🧠", "Memory Viewer", "Semantic search over chunks indexed by the Knowledge/RAG agent")

with st.container(border=True):
    col_query, col_button = st.columns([4, 1])
    query = col_query.text_input("Query", placeholder="average score in Computer Science", label_visibility="collapsed")
    col_button.write("")
    search = col_button.button("🔍 Search", disabled=not query.strip(), type="primary", use_container_width=True)

if search:
    with st.spinner("Searching memory..."):
        try:
            results = query_memory(session_id, query)
        except httpx.HTTPStatusError as exc:
            st.error(exc.response.json().get("detail", str(exc)))
            results = None
    if results is not None:
        if not results:
            st.info("No matching chunks. Has a report been generated for this session yet?")
        for hit in results:
            with st.container(border=True):
                st.write(f"**{hit['filename']}** (chunk {hit['chunk_index']}, distance {hit['distance']:.3f})")
                st.write(hit["text"])
