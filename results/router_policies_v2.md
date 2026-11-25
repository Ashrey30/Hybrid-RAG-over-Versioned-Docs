# Router vs five policies

| policy | accuracy | ci_low | ci_high | mean_tokens | p95_latency_ms |
|---|---|---|---|---|---|
| never retrieve | 0.315 | 0.225 | 0.416 | 118.326 | 415.507 |
| fixed k=2 | 0.652 | 0.551 | 0.753 | 749.910 | 1068.248 |
| fixed k=5 | 0.719 | 0.629 | 0.809 | 1572.079 | 1200.004 |
| fixed k=10 | 0.708 | 0.618 | 0.798 | 2938.337 | 1498.926 |
| oracle | 0.921 | 0.865 | 0.978 | 867.820 | 1207.153 |
| router | 0.753 | 0.663 | 0.843 | 1486.270 | 1200.126 |

Router overhead: classifier 0.12 ms; query embedding 21.2 ms (the embedding is reused by retrieval and the cache).

Label counts: {0: 19, 2: 52, 5: 16, 10: 2}
