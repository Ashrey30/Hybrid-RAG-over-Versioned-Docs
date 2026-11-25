import math

from eval.metrics import citation_hit, cohens_kappa, ndcg_at_k, percentile, recall_at_k


def test_recall():
    assert recall_at_k(["a", "b", "c"], ["b", "z"], 3) == 0.5
    assert recall_at_k(["a"], [], 5) == 0.0
    assert recall_at_k(["a", "b"], ["b"], 1) == 0.0


def test_ndcg():
    assert ndcg_at_k(["a", "x"], ["a"], 5) == 1.0
    assert math.isclose(ndcg_at_k(["x", "a"], ["a"], 5), 1 / math.log2(3))
    two = ndcg_at_k(["a", "b"], ["a", "b"], 5)
    assert math.isclose(two, 1.0)


def test_percentile_and_citation():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert math.isclose(percentile(list(range(101)), 95), 95)
    assert citation_hit(["a", "b"], ["b"]) and not citation_hit(["a"], ["b"])


def test_kappa():
    assert cohens_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert cohens_kappa([1, 1, 0, 0], [0, 0, 1, 1]) == -1.0
