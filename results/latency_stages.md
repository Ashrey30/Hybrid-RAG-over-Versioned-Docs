# Per-stage latency through the API

| stage | n | p50_ms | p95_ms |
|---|---|---|---|
| guard | 89 | 169.100 | 270.140 |
| embed | 89 | 22.600 | 39.800 |
| cache | 89 | 10.500 | 48.760 |
| total | 89 | 254.000 | 3048.860 |
| router | 23 | 0.500 | 0.990 |
| retrieve | 23 | 21.160 | 26.536 |
| generate | 23 | 459.700 | 55650.880 |
| wall clock (client) | 89 | 258.890 | 3082.626 |

Cache hit rate: 74.16%
