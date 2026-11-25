# Per-stage latency through the API

| stage | n | p50_ms | p95_ms |
|---|---|---|---|
| guard | 89 | 141.300 | 255.920 |
| embed | 89 | 19.100 | 39.700 |
| cache | 89 | 7.800 | 10.500 |
| router | 89 | 0.500 | 0.800 |
| retrieve | 78 | 8.805 | 15.718 |
| generate | 89 | 476.700 | 60683.980 |
| total | 89 | 712.900 | 60915.300 |
| wall clock (client) | 89 | 716.560 | 60919.382 |

Cache hit rate: 0.00%
