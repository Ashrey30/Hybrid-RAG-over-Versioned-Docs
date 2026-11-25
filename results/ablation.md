# Retrieval ablation (k=5)

| setup | type | n | recall@5 | ndcg@5 |
|---|---|---|---|---|
| bm25 | single | 38 | 0.895 | 0.787 |
| bm25 | ALL | 59 | 0.881 | 0.757 |
| bm25 | multi | 14 | 0.786 | 0.712 |
| bm25 | version_trap | 7 | 1.000 | 0.689 |
| dense | single | 38 | 0.947 | 0.860 |
| dense | ALL | 59 | 0.924 | 0.823 |
| dense | multi | 14 | 0.821 | 0.803 |
| dense | version_trap | 7 | 1.000 | 0.664 |
| hybrid | single | 38 | 0.921 | 0.841 |
| hybrid | ALL | 59 | 0.907 | 0.826 |
| hybrid | multi | 14 | 0.821 | 0.815 |
| hybrid | version_trap | 7 | 1.000 | 0.770 |
| hybrid_rerank | single | 38 | 0.921 | 0.867 |
| hybrid_rerank | ALL | 59 | 0.890 | 0.808 |
| hybrid_rerank | multi | 14 | 0.750 | 0.674 |
| hybrid_rerank | version_trap | 7 | 1.000 | 0.752 |

## Retrieval latency (embed + search + rerank)

| setup | p50_ms | p95_ms |
|---|---|---|
| bm25 | 5.850 | 16.904 |
| dense | 23.880 | 32.366 |
| hybrid | 27.990 | 32.348 |
| hybrid_rerank | 871.860 | 1079.736 |

## Outdated chunk in top-5 on version traps

| setting | share_of_questions |
|---|---|
| without_filter | 0.857 |
| with_filter | 0.000 |
