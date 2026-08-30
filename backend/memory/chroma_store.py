"""Chroma vector store access.

One collection per data type (see CLAUDE.md: don't mix document chunks and
social-media chunks in the same collection) — only "documents" is used so
far since the Social Intelligence Agent (Phase 4, Shohana's lane) doesn't
exist yet.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHROMA_DIR = _REPO_ROOT / "data" / "chroma_db"

CollectionName = Literal["documents", "results", "social_posts"]


@lru_cache
def get_chroma_client() -> Any:
    # Imported here, not at module level — this module gets imported
    # transitively at process startup (api.main -> routes.memory ->
    # KnowledgeRAGAgent -> here), well before any request actually touches
    # Chroma; see tools/embedding_tools.py's _get_model() for the same
    # reasoning applied to sentence-transformers/torch.
    import chromadb

    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(_CHROMA_DIR))


def get_collection(name: CollectionName) -> Any:
    """Get-or-create a named Chroma collection from the shared persistent client."""
    return get_chroma_client().get_or_create_collection(name)
