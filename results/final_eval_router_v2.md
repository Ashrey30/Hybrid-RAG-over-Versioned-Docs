# Corrected-router final evaluation

| config | n | correctness | hallucination_rate | abstention_accuracy | false_abstention_rate | citation_hit_rate | mean_tokens |
|---|---|---|---|---|---|---|---|
| baseline | 89 | 0.685 | 0.133 | 1.000 | 0.250 | 0.917 | 1566.921 |
| hybrid_k5 | 89 | 0.708 | 0.206 | 0.778 | 0.237 | 0.933 | 1593.775 |
| full_router_v2 | 89 | 0.831 | 0.145 | 0.778 | 0.100 | 0.933 | 1455.079 |

Router model: `models/router_v2.joblib`
Router output: `final_full_router_v2.jsonl`

The baseline and hybrid rows reuse the corrected results from `final_eval.md`. The router row is generated separately with the corrected-label router model.
