from agents.knowledge_rag_agent import KnowledgeRAGAgent
from graph.state import new_state


def _doc(document_id, filename, doc_type):
    return {"document_id": document_id, "filename": filename, "type": doc_type, "path": "unused"}


def test_index_document_chunks_pdf_content_and_records_output(chroma_collection, fake_embed_fn):
    agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    state = new_state(session_id="s1", goal="test")
    document = _doc("doc-1", "course_syllabus.pdf", "pdf")
    state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"pages": [{"page_number": 1, "text": "Course covers algebra and geometry.", "tables": []}]}
    }

    state = agent.index_document(state, document)

    assert state["agent_outputs"]["knowledge_rag"]["doc-1"]["chunk_count"] == 1
    assert len(state["memory_refs"]) == 1
    assert chroma_collection.count() == 1


def test_index_document_skips_when_ingestion_failed(chroma_collection, fake_embed_fn):
    agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    state = new_state(session_id="s1", goal="test")
    document = _doc("doc-missing", "bad.pdf", "pdf")

    state = agent.index_document(state, document)

    assert "knowledge_rag" not in state["agent_outputs"]
    assert chroma_collection.count() == 0


def test_index_all_indexes_every_document(chroma_collection, fake_embed_fn):
    agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    state = new_state(session_id="s1", goal="test")
    state["documents"] = [_doc("doc-1", "a.pdf", "pdf"), _doc("doc-2", "b.docx", "docx")]
    state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"pages": [{"page_number": 1, "text": "alpha content", "tables": []}]},
        "doc-2": {"paragraphs": ["beta content"], "tables": []},
    }

    state = agent.index_all(state)

    assert set(state["agent_outputs"]["knowledge_rag"]) == {"doc-1", "doc-2"}
    assert chroma_collection.count() == 2


def test_query_filters_by_allowed_document_ids(chroma_collection, fake_embed_fn):
    agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    from tools.rag_tools import index_chunks

    index_chunks(chroma_collection, "doc-mine", "mine.pdf", ["my content"], embed_fn=fake_embed_fn)
    index_chunks(chroma_collection, "doc-other", "other.pdf", ["other content"], embed_fn=fake_embed_fn)

    hits = agent.query("content", n_results=10, allowed_document_ids={"doc-mine"})

    assert len(hits) == 1
    assert hits[0]["document_id"] == "doc-mine"
