"""Learned duplicate-question check: a cross-encoder trained on Quora duplicates scores whether two questions ask
the same thing. Unlike embedding similarity it reads both questions together, so it notices swapped scopes and
opposites. Runs last, only on candidates that already passed the cheap checks."""
from __future__ import annotations

import math

from common.config import cfg


class DuplicateVerifier:
    def __init__(self, model: str | None = None, threshold: float | None = None):
        from sentence_transformers import CrossEncoder

        c = cfg()["cache"]
        self.model = CrossEncoder(model or c.get("verifier_model", "cross-encoder/quora-distilroberta-base"), device="cpu")
        self.threshold = threshold if threshold is not None else c.get("verify_threshold", 0.5)

    def scores(self, pairs: list) -> list:
        """Duplicate probability per (a, b) pair, averaged over both orders to remove order bias."""
        n = len(pairs)
        raw = self.model.predict(list(pairs) + [(b, a) for a, b in pairs], batch_size=16, show_progress_bar=False)
        vals = [float(v) if 0.0 <= float(v) <= 1.0 else 1 / (1 + math.exp(-float(v))) for v in raw]
        return [(vals[i] + vals[i + n]) / 2 for i in range(n)]

    def score(self, a: str, b: str) -> float:
        return self.scores([(a, b)])[0]

    def is_same(self, a: str, b: str) -> bool:
        return self.score(a, b) >= self.threshold
