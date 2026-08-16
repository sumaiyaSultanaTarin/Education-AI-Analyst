"""Chunking + indexing + retrieval for the Knowledge/RAG Agent.

Chroma handles vector storage; embeddings come from tools/embedding_tools.py
by default, but every function here takes an injectable `embed_fn` so tests
don't have to download the real sentence-transformers model.
"""

from typing import Any, Callable

from tools.embedding_tools import embed_texts

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100

EmbedFn = Callable[[list[str]], list[list[float]]]


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks so retrieval can return focused passages."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return chunks


def index_chunks(
    collection: Any,
    document_id: str,
    filename: str,
    chunks: list[str],
    embed_fn: EmbedFn = embed_texts,
) -> list[str]:
    """Embed and store chunks in a Chroma collection, tagged for citation lookup.

    Returns the Chroma ids written (empty list if there were no chunks).
    """
    if not chunks:
        return []

    ids = [f"{document_id}::chunk-{i}" for i in range(len(chunks))]
    embeddings = embed_fn(chunks)
    metadatas = [
        {"document_id": document_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    return ids


def query_collection(
    collection: Any,
    query: str,
    n_results: int = 5,
    embed_fn: EmbedFn = embed_texts,
) -> list[dict]:
    """Semantic search over a collection.

    Returns [{"text", "filename", "document_id", "chunk_index", "distance"}],
    empty if the collection has nothing indexed yet.
    """
    count = collection.count()
    if count == 0:
        return []

    query_embedding = embed_fn([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding], n_results=min(n_results, count)
    )

    hits = []
    for text, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({
            "text": text,
            "filename": metadata["filename"],
            "document_id": metadata["document_id"],
            "chunk_index": metadata["chunk_index"],
            "distance": distance,
        })
    return hits
