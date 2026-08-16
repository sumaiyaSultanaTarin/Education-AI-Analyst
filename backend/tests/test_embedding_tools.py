"""Tests for tools/embedding_tools.py.

Monkeypatches SentenceTransformer itself rather than downloading the real
all-MiniLM-L6-v2 model — keeps this test fast and offline (no HuggingFace
Hub access needed in CI), while still exercising the actual embed_texts
code path (batching, empty-input short-circuit, numpy-to-list conversion).
"""

import numpy as np

import tools.embedding_tools as embedding_tools


class _FakeModel:
    def encode(self, texts):
        # Real SentenceTransformer.encode() returns a numpy array, and
        # embed_texts() calls .tolist() on each row — match that shape.
        return np.array([[float(len(text)), 0.0, 1.0] for text in texts])


def test_embed_texts_returns_one_vector_per_text(monkeypatch):
    monkeypatch.setattr(embedding_tools, "_get_model", lambda: _FakeModel())

    vectors = embedding_tools.embed_texts(["hi", "a longer chunk of text"])

    assert len(vectors) == 2
    assert vectors[0] == [2.0, 0.0, 1.0]
    assert vectors[1][0] == 22.0


def test_embed_texts_empty_input_returns_no_vectors(monkeypatch):
    monkeypatch.setattr(embedding_tools, "_get_model", lambda: _FakeModel())

    assert embedding_tools.embed_texts([]) == []


def test_get_model_is_cached(monkeypatch):
    # _get_model is @lru_cache'd — calling it twice must return the same
    # instance rather than reloading the model from disk/network each time.
    # Patch the constructor itself (not the SentenceTransformer.encode result)
    # so this doesn't need real model weights.
    embedding_tools._get_model.cache_clear()
    calls = []
    monkeypatch.setattr(
        embedding_tools, "SentenceTransformer", lambda name: calls.append(name) or _FakeModel()
    )

    first = embedding_tools._get_model()
    second = embedding_tools._get_model()

    assert first is second
    assert len(calls) == 1
    embedding_tools._get_model.cache_clear()
