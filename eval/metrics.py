"""Retrieval and latency metrics in plain Python (no heavy deps, so CI can test them)."""
from __future__ import annotations

import math


def recall_at_k(retrieved: list, gold: list, k: int) -> float:
    if not gold:
        return 0.0
    return len(set(retrieved[:k]) & set(gold)) / len(set(gold))


def ndcg_at_k(retrieved: list, gold: list, k: int) -> float:
    g = set(gold)
    if not g:
        return 0.0
    dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(retrieved[:k]) if r in g)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(g), k)))
    return dcg / idcg


def citation_hit(cited: list, gold: list) -> bool:
    return bool(set(cited) & set(gold))


def percentile(values: list, p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    pos = (len(s) - 1) * p / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def cohens_kappa(a: list, b: list) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n
    labels = set(a) | set(b)
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
