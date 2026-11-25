# Injection guard (Prompt Guard 2)

AUROC 0.898; 60 attacks, 145 benign prompts; latency p50 141 ms, p95 227 ms. Benign prompts include the golden questions used to pick the threshold, so recall at the chosen threshold is optimistic.

| threshold | block_rate_attacks | false_positive_rate_benign |
|---|---|---|
| 1e-05 | 1.000 | 1.000 |
| 0.0001 | 1.000 | 1.000 |
| 0.0005 | 0.900 | 0.503 |
| 0.001 | 0.633 | 0.028 |
| 0.0011 (benign p99) | 0.617 | 0.014 |
| 0.005 | 0.333 | 0.000 |
| 0.01 | 0.250 | 0.000 |
| 0.05 | 0.183 | 0.000 |
| 0.1 | 0.167 | 0.000 |
| 0.3 | 0.133 | 0.000 |
| 0.5 | 0.133 | 0.000 |
| 0.9 | 0.117 | 0.000 |
