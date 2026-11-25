"""Local CPU models: dense (bge-small) and sparse BM25 (fastembed). Loaded lazily."""
from __future__ import annotations

import numpy as np

from common.config import cfg

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_dense = None
_sparse = None


def _st():
    global _dense
    if _dense is None:
        from sentence_transformers import SentenceTransformer

        _dense = SentenceTransformer(cfg()["models"]["embedding"], device="cpu")
    return _dense


def embed_query(text: str) -> np.ndarray:
    return _st().encode(QUERY_PREFIX + text, normalize_embeddings=True).astype(np.float32)


def embed_queries(texts: list[str], batch_size: int = 32) -> np.ndarray:
    return _st().encode([QUERY_PREFIX + t for t in texts], batch_size=batch_size, normalize_embeddings=True).astype(np.float32)


def embed_passages(texts: list[str], batch_size: int = 32) -> np.ndarray:
    return _st().encode(texts, batch_size=batch_size, normalize_embeddings=True).astype(np.float32)


def _sp():
    global _sparse
    if _sparse is None:
        from fastembed import SparseTextEmbedding

        _sparse = SparseTextEmbedding("Qdrant/bm25")
    return _sparse


def sparse_passages(texts: list[str]):
    """Returns a list of (indices, values) for each passage."""
    return [(e.indices.tolist(), e.values.tolist()) for e in _sp().passage_embed(texts)]


def sparse_query(text: str):
    e = next(iter(_sp().query_embed(text)))
    return e.indices.tolist(), e.values.tolist()
