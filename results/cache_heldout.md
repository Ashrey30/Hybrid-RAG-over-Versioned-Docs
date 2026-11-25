# Semantic cache: stage-by-stage (15 pairs, split=heldout)

| threshold | sim_hit | sim_false | +entity_hit | +entity_false | +retrieval_hit | +retrieval_false |
|---|---|---|---|---|---|---|
| 0.800 | 1.000 | 1.000 | 1.000 | 0.533 | 1.000 | 0.467 |
| 0.840 | 1.000 | 1.000 | 1.000 | 0.533 | 1.000 | 0.467 |
| 0.860 | 1.000 | 1.000 | 1.000 | 0.533 | 1.000 | 0.467 |
| 0.880 | 1.000 | 1.000 | 1.000 | 0.533 | 1.000 | 0.467 |
| 0.900 | 0.933 | 0.867 | 0.933 | 0.467 | 0.933 | 0.400 |
| 0.920 | 0.933 | 0.800 | 0.933 | 0.467 | 0.933 | 0.400 |
| 0.940 | 0.800 | 0.733 | 0.800 | 0.467 | 0.800 | 0.400 |
| 0.960 | 0.600 | 0.333 | 0.600 | 0.333 | 0.600 | 0.333 |

Hit = paraphrase served; false = near-miss served (wrong answer). One pair is 6.7 points.

Verified hit costs about 160 ms (embedding 137, lookup 2.9, retrieval 20) against 590 ms uncached, saving about 430 ms.

At the configured threshold 0.88: hit 100.0%, false 46.7%.

Near-misses still served:
- I want to create a PersistentVolumeClaim that populates its volume from a VolumeSnapshot located in the same namespace. What resources must I create to allow this same‑namespace reference, and how can I ensure that the cluster will warn me if the appropriate volume populator is missing?
- What annotation should I add to a Kubernetes Service manifest to create an external load balancer on Google Kubernetes Engine (GKE)?
- How can I contact the Kubernetes team for help when my Service is not working despite pods, endpoints, DNS, and kube-proxy all appearing unhealthy?
- How can I grant read‑only permissions to all service accounts in a single namespace in my Kubernetes cluster?
- Is it allowed to specify both the Terminating and NotTerminating scopes in a single LimitRange?
- What kubectl command can I use to view the logs of a specific deployment when troubleshooting container crashes?
- What are the purposes and current statuses of the `endpoints.kubernetes.io/over-capacity` and `control-plane.alpha.kubernetes.io/leader` annotations on Service objects, and how do they differ in terms of what information they convey and whether they are still used by the Kubernetes control plane?
