# Semantic cache: stage-by-stage (41 pairs, split=development)

| threshold | sim_hit | sim_false | +entity_hit | +entity_false | +retrieval_hit | +retrieval_false | +verifier_hit | +verifier_false |
|---|---|---|---|---|---|---|---|---|
| 0.800 | 1.000 | 0.976 | 1.000 | 0.244 | 0.951 | 0.195 | 0.829 | 0.049 |
| 0.840 | 1.000 | 0.976 | 1.000 | 0.244 | 0.951 | 0.195 | 0.829 | 0.049 |
| 0.860 | 1.000 | 0.951 | 1.000 | 0.244 | 0.951 | 0.195 | 0.829 | 0.049 |
| 0.880 | 0.951 | 0.927 | 0.951 | 0.244 | 0.902 | 0.195 | 0.780 | 0.049 |
| 0.900 | 0.902 | 0.878 | 0.902 | 0.220 | 0.854 | 0.171 | 0.756 | 0.049 |
| 0.920 | 0.805 | 0.683 | 0.805 | 0.220 | 0.780 | 0.171 | 0.707 | 0.049 |
| 0.940 | 0.707 | 0.537 | 0.707 | 0.195 | 0.683 | 0.171 | 0.634 | 0.049 |
| 0.960 | 0.512 | 0.293 | 0.512 | 0.122 | 0.488 | 0.122 | 0.463 | 0.049 |

## Verifier threshold sweep (similarity threshold 0.88)

| verify_threshold | verifier_only_hit | verifier_only_false | all_stages_hit | all_stages_false |
|---|---|---|---|---|
| 0.050 | 0.951 | 0.317 | 0.902 | 0.073 |
| 0.100 | 0.951 | 0.268 | 0.902 | 0.073 |
| 0.200 | 0.902 | 0.220 | 0.854 | 0.073 |
| 0.300 | 0.902 | 0.220 | 0.854 | 0.073 |
| 0.400 | 0.854 | 0.220 | 0.805 | 0.073 |
| 0.500 | 0.829 | 0.122 | 0.780 | 0.049 |
| 0.600 | 0.805 | 0.122 | 0.756 | 0.049 |
| 0.700 | 0.780 | 0.073 | 0.756 | 0.024 |
| 0.800 | 0.732 | 0.073 | 0.707 | 0.024 |
| 0.900 | 0.683 | 0.073 | 0.659 | 0.024 |

Hit = paraphrase served; false = near-miss served (wrong answer). One pair is 2.4 points.

Verified hit costs about 83 ms (embedding 22, lookup 1.3, retrieval 16, verifier 44) against 590 ms uncached, saving about 506 ms.

At the configured thresholds (similarity 0.88, verifier 0.5): hit 78.0%, false 4.9%.

Near-misses still served:
- How can I grant read‑only permissions to all service accounts in a single namespace in my Kubernetes cluster?
- What are the purposes and current statuses of the `endpoints.kubernetes.io/over-capacity` and `control-plane.alpha.kubernetes.io/leader` annotations on Service objects, and how do they differ in terms of what information they convey and whether they are still used by the Kubernetes control plane?
