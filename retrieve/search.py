"""Four retrieval setups over one Qdrant collection: bm25, dense, hybrid (RRF), hybrid + cross-encoder rerank."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from qdrant_client import QdrantClient, models

from common.config import cfg, qdrant_url
from common.embed import embed_query, sparse_query
from guard.access import allowed_groups

MODES = ("bm25", "dense", "hybrid", "hybrid_rerank")
_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(cfg()["models"]["reranker"], device="cpu", max_length=512)
    return _reranker


@dataclass
class Hit:
    chunk_id: str
    score: float
    payload: dict


@dataclass
class RetrievalResult:
    hits: list[Hit]
    timings_ms: dict = field(default_factory=dict)

    @property
    def total_ms(self) -> float:
        return sum(self.timings_ms.values())


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)


class Retriever:
    def __init__(self, client: QdrantClient | None = None, collection: str | None = None):
        self.client = client or QdrantClient(url=qdrant_url(), timeout=60, check_compatibility=False)
        self.collection = collection or cfg()["qdrant"]["collection"]
        self.candidates = cfg()["retrieval"]["candidates"]

    @staticmethod
    def make_filter(user_group: str, latest_only: bool) -> models.Filter:
        """The access filter runs *inside* the search, so restricted chunks are never retrieved."""
        must = [models.FieldCondition(key="access_group", match=models.MatchAny(any=allowed_groups(user_group)))]
        if latest_only:
            must.append(models.FieldCondition(key="is_latest", match=models.MatchValue(value=True)))
        return models.Filter(must=must)

    def retrieve(self, query: str, mode: str = "hybrid_rerank", k: int = 5, user_group: str = "public",
                 latest_only: bool = True, qvec=None) -> RetrievalResult:
        assert mode in MODES, mode
        flt = self.make_filter(user_group, latest_only)
        t: dict = {}
        if mode != "bm25" and qvec is None:
            s = time.perf_counter()
            qvec = embed_query(query)
            t["embed"] = _ms(s)

        s = time.perf_counter()
        if mode == "dense":
            res = self.client.query_points(self.collection, query=qvec.tolist(), using="dense",
                                           query_filter=flt, limit=k, with_payload=True)
        elif mode == "bm25":
            idx, val = sparse_query(query)
            res = self.client.query_points(self.collection, query=models.SparseVector(indices=idx, values=val),
                                           using="bm25", query_filter=flt, limit=k, with_payload=True)
        else:
            idx, val = sparse_query(query)
            cand = self.candidates
            res = self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=qvec.tolist(), using="dense", filter=flt, limit=cand),
                    models.Prefetch(query=models.SparseVector(indices=idx, values=val), using="bm25", filter=flt, limit=cand),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                query_filter=flt,
                limit=cand if mode == "hybrid_rerank" else k,
                with_payload=True,
            )
        t["retrieve"] = _ms(s)
        hits = [Hit(p.payload["chunk_id"], float(p.score), p.payload) for p in res.points]

        if mode == "hybrid_rerank" and hits:
            s = time.perf_counter()
            scores = get_reranker().predict([(query, h.payload["text"]) for h in hits])
            for h, sc in zip(hits, scores):
                h.score = float(sc)
            hits.sort(key=lambda h: h.score, reverse=True)
            t["rerank"] = _ms(s)
        return RetrievalResult(hits[:k], t)
