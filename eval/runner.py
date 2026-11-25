"""One question -> retrieve -> generate -> score retrieval. Shared by baseline, k-sweep, stale and final evals."""
from __future__ import annotations

from eval.metrics import citation_hit, ndcg_at_k, recall_at_k
from generate.answer import generate_answer
from generate.citations import check_citations


def answer_one(q: dict, retriever, llm, mode: str, k: int, latest_only: bool, user_group: str = "restricted") -> dict:
    hits, timings = [], {}
    if k > 0:
        res = retriever.retrieve(q["question"], mode, k, user_group, latest_only)
        hits, timings = res.hits, res.timings_ms
    gen = generate_answer(llm, q["question"], hits)
    ids = [h.chunk_id for h in hits]
    gold = q.get("gold_chunk_ids") or []
    clean, valid, stripped = check_citations(gen.text, set(ids))
    rec = {
        "id": q["id"], "type": q["type"], "mode": mode, "k": k, "latest_only": latest_only,
        "retrieved_ids": ids, "answer": gen.text, "clean_answer": clean, "status": gen.status,
        "cited_ids": valid, "stripped_ids": stripped,
        "cited_stale": any(not h.payload["is_latest"] for h in hits if h.chunk_id in valid),
        "tokens": gen.tokens, "gen_latency_ms": gen.latency_ms,
        "retrieve_ms": sum(timings.values()), "contexts": [h.payload["text"] for h in hits],
    }
    if gold and k > 0:
        rec["recall"] = recall_at_k(ids, gold, k)
        rec["ndcg"] = ndcg_at_k(ids, gold, k)
        rec["citation_hit"] = citation_hit(valid, gold)
    elif gold:
        rec["recall"], rec["ndcg"], rec["citation_hit"] = 0.0, 0.0, False
    return rec
