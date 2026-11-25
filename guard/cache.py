"""Semantic cache in Qdrant, keyed by access group and corpus version."""
from __future__ import annotations

import time
import uuid

from qdrant_client import QdrantClient, models

from common.cache_identity import corpus_fingerprint, runtime_fingerprint
from common.config import cfg, qdrant_url
from guard.match import normalize_question


class SemanticCache:
    def __init__(self, client: QdrantClient | None = None, threshold: float | None = None, version: str | None = None):
        c = cfg()["cache"]
        self.client = client or QdrantClient(url=qdrant_url(), check_compatibility=False)
        self.name = c["collection"]
        self.threshold = threshold if threshold is not None else c["threshold"]
        self.version = version or corpus_fingerprint()
        self.runtime = runtime_fingerprint()

    def ensure(self) -> None:
        if not self.client.collection_exists(self.name):
            self.client.create_collection(
                self.name, vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )
            self.client.create_payload_index(self.name, "access_group", models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(self.name, "corpus_version", models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(self.name, "runtime_fingerprint", models.PayloadSchemaType.KEYWORD)

    def _filter(self, group: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(key="access_group", match=models.MatchValue(value=group)),
                models.FieldCondition(key="corpus_version", match=models.MatchValue(value=self.version)),
                models.FieldCondition(key="runtime_fingerprint", match=models.MatchValue(value=self.runtime)),
            ]
        )

    def _point_id(self, group: str, question: str) -> str:
        """Deterministic ID per (corpus version, group, normalised question): storing again overwrites, and it
        doubles as the key of the exact-match tier."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.version}|{group}|{normalize_question(question)}"))

    def lookup_exact(self, question: str, group: str) -> dict | None:
        if not self.client.collection_exists(self.name):
            self.ensure()
        res = self.client.retrieve(self.name, ids=[self._point_id(group, question)], with_payload=True)
        if not res:
            return None
        payload = res[0].payload
        if payload.get("corpus_version") != self.version:
            return None
        if payload.get("runtime_fingerprint") != self.runtime:
            return None
        return {"score": 1.0, **payload}

    def lookup(self, qvec, group: str, limit: int = 5) -> list[dict]:
        if not self.client.collection_exists(self.name):
            self.ensure()
        res = self.client.query_points(
            self.name, query=qvec.tolist(), query_filter=self._filter(group), limit=limit,
            score_threshold=self.threshold, with_payload=True,
        )
        return [{"score": p.score, **p.payload} for p in res.points] if res.points else []

    def store(self, qvec, group: str, question: str, entry: dict) -> None:
        if not self.client.collection_exists(self.name):
            self.ensure()
        payload = {
            "question": question,
            "access_group": group,
            "corpus_version": self.version,
            "runtime_fingerprint": self.runtime,
            "ts": time.time(),
            **entry,
        }
        self.client.upsert(
            self.name, points=[models.PointStruct(id=self._point_id(group, question), vector=qvec.tolist(), payload=payload)], wait=True
        )
