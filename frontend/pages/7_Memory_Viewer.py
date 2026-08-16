"""Query the Chroma vector store for this session's indexed document chunks."""

import httpx
import streamlit as st
from utils.api_client import query_memory
from utils.session_state import require_session_id

st.set_page_config(page_title="Memory Viewer", page_icon="🧠")
session_id = require_session_id()
st.title("Memory Viewer")
st.caption("Semantic search over chunks indexed by the Knowledge/RAG agent (run intake + generate a report first).")

query = st.text_input("Query", placeholder="average score in Computer Science")
if st.button("Search", disabled=not query.strip()):
    try:
        results = query_memory(session_id, query)
    except httpx.HTTPStatusError as exc:
        st.error(exc.response.json().get("detail", str(exc)))
    else:
        if not results:
            st.info("No matching chunks. Has a report been generated for this session yet?")
        for hit in results:
            with st.container(border=True):
                st.write(f"**{hit['filename']}** (chunk {hit['chunk_index']}, distance {hit['distance']:.3f})")
                st.write(hit["text"])
