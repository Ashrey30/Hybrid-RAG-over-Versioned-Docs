# Final evaluation

| config | n | correctness | hallucination_rate | abstention_accuracy | false_abstention_rate | citation_hit_rate | mean_tokens |
|---|---|---|---|---|---|---|---|
| baseline | 89 | 0.685 | 0.133 | 1.000 | 0.250 | 0.917 | 1566.921 |
| hybrid_k5 | 89 | 0.708 | 0.206 | 0.778 | 0.237 | 0.933 | 1593.775 |
| full_router (pre-corrected-label model) | 89 | 0.820 | 0.145 | 0.778 | 0.113 | 0.933 | 1490.517 |

Post-hoc audit correction: `una-095` was reclassified from unanswerable to answerable (`multi`) based on its retrieved source passages. Existing generated answers and faithfulness scores were retained; the affected correctness, abstention, retrieval, and citation metrics were recalculated. See the project progress report for the audit details and limitations.

The router row above uses the model active during the original final run. The corrected-label model was subsequently evaluated end to end; see `results/final_eval_router_v2.md` and `results/final_full_router_v2.jsonl`. It scored 0.831 correctness, 0.145 faithfulness<1, 0.778 abstention accuracy, 0.100 false-abstention rate, 0.933 citation hit rate, and 1455.079 mean tokens on the same audited 89-question development set. The app now uses `models/router_v2.joblib`, selected in `config.yaml` and verified in the rebuilt API container.
