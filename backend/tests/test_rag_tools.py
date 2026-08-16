from tools.rag_tools import chunk_text, index_chunks, query_collection


def test_chunk_text_splits_long_text_with_overlap():
    text = "x" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 400 for chunk in chunks)
    assert "".join(chunks).startswith("x")


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("   ") == []


def test_index_and_query_round_trip(chroma_collection, fake_embed_fn):
    chunks = ["late assignment submissions rose in March", "attendance was steady"]

    ids = index_chunks(
        chroma_collection, "doc-1", "report.pdf", chunks, embed_fn=fake_embed_fn
    )

    assert len(ids) == 2
    assert chroma_collection.count() == 2

    hits = query_collection(
        chroma_collection, "late submissions", n_results=5, embed_fn=fake_embed_fn
    )

    assert len(hits) == 2
    assert {hit["filename"] for hit in hits} == {"report.pdf"}
    assert {hit["document_id"] for hit in hits} == {"doc-1"}


def test_query_empty_collection_returns_no_hits(chroma_collection, fake_embed_fn):
    assert query_collection(chroma_collection, "anything", embed_fn=fake_embed_fn) == []


def test_index_chunks_with_no_chunks_is_a_noop(chroma_collection, fake_embed_fn):
    ids = index_chunks(chroma_collection, "doc-1", "empty.pdf", [], embed_fn=fake_embed_fn)

    assert ids == []
    assert chroma_collection.count() == 0
