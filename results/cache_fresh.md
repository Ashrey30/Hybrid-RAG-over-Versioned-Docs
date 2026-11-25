# Semantic cache: stage-by-stage (45 pairs, split=fresh)

| threshold | sim_hit | sim_false | +entity_hit | +entity_false | +retrieval_hit | +retrieval_false | +verifier_hit | +verifier_false |
|---|---|---|---|---|---|---|---|---|
| 0.800 | 0.956 | 0.956 | 0.889 | 0.511 | 0.778 | 0.422 | 0.533 | 0.156 |
| 0.840 | 0.911 | 0.800 | 0.844 | 0.422 | 0.733 | 0.356 | 0.511 | 0.156 |
| 0.860 | 0.867 | 0.733 | 0.800 | 0.400 | 0.711 | 0.333 | 0.511 | 0.156 |
| 0.880 | 0.778 | 0.667 | 0.711 | 0.378 | 0.667 | 0.333 | 0.511 | 0.156 |
| 0.900 | 0.733 | 0.556 | 0.711 | 0.333 | 0.667 | 0.289 | 0.511 | 0.133 |
| 0.920 | 0.667 | 0.444 | 0.644 | 0.244 | 0.600 | 0.200 | 0.467 | 0.089 |
| 0.940 | 0.511 | 0.400 | 0.489 | 0.222 | 0.444 | 0.178 | 0.356 | 0.089 |
| 0.960 | 0.222 | 0.222 | 0.200 | 0.111 | 0.156 | 0.111 | 0.133 | 0.067 |

## Verifier threshold sweep (similarity threshold 0.88)

| verify_threshold | verifier_only_hit | verifier_only_false | all_stages_hit | all_stages_false |
|---|---|---|---|---|
| 0.050 | 0.711 | 0.267 | 0.622 | 0.200 |
| 0.100 | 0.711 | 0.244 | 0.622 | 0.178 |
| 0.200 | 0.667 | 0.222 | 0.578 | 0.178 |
| 0.300 | 0.644 | 0.222 | 0.556 | 0.178 |
| 0.400 | 0.600 | 0.222 | 0.511 | 0.178 |
| 0.500 | 0.578 | 0.200 | 0.511 | 0.156 |
| 0.600 | 0.556 | 0.178 | 0.489 | 0.156 |
| 0.700 | 0.556 | 0.111 | 0.489 | 0.089 |
| 0.800 | 0.533 | 0.111 | 0.467 | 0.089 |
| 0.900 | 0.422 | 0.067 | 0.356 | 0.044 |

Hit = paraphrase served; false = near-miss served (wrong answer). One pair is 2.2 points.

Verified hit costs about 259 ms (embedding 68, lookup 4.6, retrieval 77, verifier 110) against 590 ms uncached, saving about 330 ms.

At the configured thresholds (similarity 0.88, verifier 0.5): hit 51.1%, false 15.6%.

Near-misses still served:
- According to the version skew policy, which Kubernetes component versions can kubeadm use that are one version newer than its own version?
- What command is used to create a connection that reroutes remote service traffic to a local service?
- What does the WaitForAllControlPlaneComponents feature gate cause kubeadm to wait for during kubeadm join?
- According to the passage, when is it appropriate to use a Deployment rather than a DaemonSet?
- What command can you run inside the ephemeral container to view its granted security context?
- When is a variable defined in a Validating Admission Policy?
- Which signal does kubelet send after the grace period has expired to any remaining processes during pod termination?
