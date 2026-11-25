# Router vs five policies

| policy | accuracy | ci_low | ci_high | mean_tokens | p95_latency_ms |
|---|---|---|---|---|---|
| never retrieve | 0.326 | 0.236 | 0.427 | 118.326 | 415.507 |
| fixed k=2 | 0.663 | 0.562 | 0.764 | 749.910 | 1068.248 |
| fixed k=5 | 0.708 | 0.618 | 0.798 | 1572.079 | 1200.004 |
| fixed k=10 | 0.697 | 0.607 | 0.798 | 2938.337 | 1498.926 |
| oracle | 0.933 | 0.876 | 0.978 | 781.180 | 1148.979 |
| router | 0.640 | 0.539 | 0.742 | 1105.461 | 1095.329 |

Router overhead: classifier 0.21 ms; query embedding 37.3 ms (the embedding is reused by retrieval and the cache).

Label counts: {0: 29, 2: 44, 5: 14, 10: 2}
