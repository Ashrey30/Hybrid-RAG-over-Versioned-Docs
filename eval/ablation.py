"""Retrieval ablation with no LLM calls: BM25 vs dense vs hybrid (RRF) vs hybrid + rerank, plus the stale-chunk test.

Run:  python -m eval.ablation
"""
from __future__ import annotations

import json

from common.config import results_dir
from common.io import md_table
from eval.golden import NEEDS_RETRIEVAL, load_golden
from eval.metrics import mean, ndcg_at_k, percentile, recall_at_k
from retrieve.search import MODES, Retriever

K = 5


def main() -> None:
    qs = [q for q in load_golden() if q["type"] in NEEDS_RETRIEVAL and q.get("gold_chunk_ids")]
    R = Retriever()
    for q in qs[:5]:                          # warm-up: load models, fill caches
        for m in MODES:
            R.retrieve(q["question"], m, K, "restricted", latest_only=False)

    rows, lat_rows = [], []
    for mode in MODES:
        per = {}
        lats = []
        for q in qs:
            res = R.retrieve(q["question"], mode, K, "restricted", latest_only=False)
            ids = [h.chunk_id for h in res.hits]
            per.setdefault(q["type"], []).append((recall_at_k(ids, q["gold_chunk_ids"], K), ndcg_at_k(ids, q["gold_chunk_ids"], K)))
            per.setdefault("ALL", []).append(per[q["type"]][-1])
            lats.append(res.total_ms)
        for t, v in per.items():
            rows.append({"setup": mode, "type": t, "n": len(v), "recall@5": mean([x[0] for x in v]), "ndcg@5": mean([x[1] for x in v])})
        lat_rows.append({"setup": mode, "p50_ms": percentile(lats, 50), "p95_ms": percentile(lats, 95)})

    # stale chunks reaching the top-5 on version traps, before / after the is_latest filter
    traps = [q for q in load_golden() if q["type"] == "version_trap"]
    stale = {}
    for label, latest in (("without_filter", False), ("with_filter", True)):
        hit = 0
        for q in traps:
            res = R.retrieve(q["question"], "hybrid_rerank", K, "restricted", latest_only=latest)
            hit += any(not h.payload["is_latest"] for h in res.hits)
        stale[label] = hit / max(len(traps), 1)

    out = results_dir()
    (out / "ablation.json").write_text(json.dumps({"quality": rows, "latency": lat_rows, "stale_in_top5": stale}, indent=2))
    md = ("# Retrieval ablation (k=5)\n\n" + md_table(rows) + "\n## Retrieval latency (embed + search + rerank)\n\n"
          + md_table(lat_rows) + "\n## Outdated chunk in top-5 on version traps\n\n" + md_table([{"setting": k, "share_of_questions": v} for k, v in stale.items()]))
    (out / "ablation.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
