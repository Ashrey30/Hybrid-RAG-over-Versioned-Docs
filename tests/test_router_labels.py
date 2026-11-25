from retrieve.router import choose_k, label_min_k
from api.pipeline import retrieval_k_for_question


def test_label_is_smallest_correct_k():
    assert label_min_k({0: False, 2: True, 5: True, 10: True}) == 2
    assert label_min_k({0: True, 2: False}) == 0


def test_label_falls_back_to_5():
    assert label_min_k({0: False, 2: False, 5: False, 10: False}) == 5


def test_unsure_picks_higher_k():
    classes = [0, 2, 5, 10]
    assert choose_k([0.1, 0.4, 0.45, 0.05], classes, 0.5) == 5
    assert choose_k([0.1, 0.7, 0.15, 0.05], classes, 0.5) == 2


def test_multi_part_question_keeps_broad_retrieval():
    question = (
        "Why does this happen, and once the condition stabilizes, "
        "which pods are evicted first?"
    )
    assert retrieval_k_for_question(question, 5) == 10
    assert retrieval_k_for_question("What command starts a pod?", 5) == 5
