"""Local sentence-transformers embeddings.

The one place in the project that loads its own model instead of going
through core/llm_client.py — OpenRouter doesn't serve embeddings (see
CLAUDE.md), so this has to be a local, non-API model.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache
def _get_model() -> "SentenceTransformer":
    # Imported here, not at module level: sentence-transformers pulls in
    # torch, whose own import alone (never mind loading the model) is
    # heavy enough to matter on a memory-constrained host — this module
    # gets imported transitively by api.main at process startup
    # (routes.memory -> KnowledgeRAGAgent -> here), well before any RAG
    # call actually happens, so an eager import here was paying that cost
    # on every single request the app serves, not just RAG ones.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text chunks into vectors for Chroma storage/queries."""
    if not texts:
        return []
    return [vector.tolist() for vector in _get_model().encode(texts)]
