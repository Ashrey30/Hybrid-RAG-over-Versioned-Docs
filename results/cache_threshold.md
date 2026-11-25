# Semantic cache: stage-by-stage (26 pairs)

| threshold | sim_hit | sim_false | +entity_hit | +entity_false | +retrieval_hit | +retrieval_false |
|---|---|---|---|---|---|---|
| 0.800 | 1.000 | 0.962 | 1.000 | 0.077 | 0.923 | 0.038 |
| 0.840 | 1.000 | 0.962 | 1.000 | 0.077 | 0.923 | 0.038 |
| 0.860 | 1.000 | 0.923 | 1.000 | 0.077 | 0.923 | 0.038 |
| 0.880 | 0.923 | 0.885 | 0.923 | 0.077 | 0.846 | 0.038 |
| 0.900 | 0.885 | 0.885 | 0.885 | 0.077 | 0.808 | 0.038 |
| 0.920 | 0.731 | 0.615 | 0.731 | 0.077 | 0.692 | 0.038 |
| 0.940 | 0.654 | 0.423 | 0.654 | 0.038 | 0.615 | 0.038 |
| 0.960 | 0.462 | 0.269 | 0.462 | 0.000 | 0.423 | 0.000 |

Hit = paraphrase served; false = near-miss served (wrong answer). One pair is 3.8 points.

Verified hit costs about 35 ms (embedding 22, lookup 1.2, retrieval 12) against 590 ms uncached, saving about 554 ms.

At the configured threshold 0.88: hit 84.6%, false 3.8%.

Near-misses still served:
- What are the two approaches for creating a highly available Kubernetes cluster with kubeadm, and how do they differ in terms of network plugin selection and component placement?
