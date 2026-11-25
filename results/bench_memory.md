# Memory, disk and build time

| m | mode | ram_mb | disk_mb | graph_build_s | quant_build_s |
|---|---|---|---|---|---|
| 8 | binary | 3308 | 3126 | 492 | 37 |
| 8 | float32 | 3115 | 3023 | 492 | 0 |
| 8 | scalar | 3887 | 3758 | 492 | 56 |
| 16 | binary | 3282 | 3146 | 494 | 54 |
| 16 | float32 | 3131 | 3031 | 494 | 0 |
| 16 | scalar | 3865 | 3762 | 494 | 74 |
| 32 | binary | 3339 | 3165 | 531 | 66 |
| 32 | float32 | 3141 | 3035 | 531 | 0 |
| 32 | scalar | 3875 | 3767 | 531 | 86 |

## Candidate settings (recall@10 >= 0.95)

| criterion | m | mode | ef | recall10 | p50_ms | p95_ms | ram_mb | disk_mb |
|---|---|---|---|---|---|---|---|---|
| lowest RAM | 16 | float32 | 128 | 0.966 | 5.850 | 8.230 | 3126 | 3031 |
| lowest p95 | 32 | scalar | 64 | 0.969 | 4.430 | 5.830 | 3875 | 3767 |

Latency is Qdrant's server-side search time. Write the reason for your recommendation yourself in the README.
