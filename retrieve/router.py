"""Adaptive retrieval router: logistic regression on the query embedding picks k in {0, 2, 5, 10}."""
from __future__ import annotations

from common.config import ROOT, cfg

KS = (0, 2, 5, 10)


def label_min_k(correct_by_k: dict, ks=KS, fallback: int = 5) -> int:
    """Smallest k that gave a correct answer; if none did, the fallback (5)."""
    for k in sorted(ks):
        if correct_by_k.get(k):
            return k
    return fallback


def choose_k(proba, classes, min_confidence: float = 0.5) -> int:
    """argmax class; when unsure (max prob below threshold) take the higher k of the top-2 classes."""
    order = sorted(range(len(classes)), key=lambda i: proba[i], reverse=True)
    if proba[order[0]] >= min_confidence or len(order) == 1:
        return int(classes[order[0]])
    return int(max(classes[order[0]], classes[order[1]]))


class Router:
    def __init__(self, clf, min_confidence: float | None = None):
        self.clf = clf
        self.min_confidence = min_confidence if min_confidence is not None else cfg()["router"]["min_confidence"]

    @classmethod
    def load(cls, path=None) -> "Router":
        import joblib

        p = ROOT / (path or cfg()["router"]["path"])
        return cls(joblib.load(p))

    def predict_k(self, qvec) -> int:
        proba = self.clf.predict_proba(qvec.reshape(1, -1))[0]
        return choose_k(proba, self.clf.classes_, self.min_confidence)
