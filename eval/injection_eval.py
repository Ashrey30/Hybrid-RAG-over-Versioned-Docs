"""Prompt Guard on a public injection dataset + your benign golden questions.
Scores every text once, then reports block rate / false-positive rate across thresholds, AUROC and added latency.
Run: python -m eval.injection_eval
"""
from __future__ import annotations

import json
import time

from common.config import results_dir
from common.io import md_table
from eval.golden import load_golden
from eval.metrics import mean, percentile
from guard.injection import InjectionGuard

THRESHOLDS = [1e-5, 1e-4, 5e-4, 1e-3, 5e-3, 0.01, 0.05, 0.1, 0.3, 0.5, 0.9]


def main() -> None:
    from datasets import load_dataset
    from sklearn.metrics import roc_auc_score

    ds = load_dataset("deepset/prompt-injections", split="test")   # columns: text, label (1 = injection)
    G = InjectionGuard()
    G.score("warm up")
    lat: list[float] = []

    def scores(texts):
        out = []
        for t in texts:
            s = time.perf_counter()
            out.append(G.score(t))
            lat.append((time.perf_counter() - s) * 1000)
        return out

    sa = scores([r["text"] for r in ds if r["label"] == 1])
    benign = scores([r["text"] for r in ds if r["label"] == 0]) + scores([q["question"] for q in load_golden()])

    p99 = percentile(benign, 99)          # data-driven operating point: ~1% of benign prompts scored above it
    thresholds = sorted(set(THRESHOLDS + [p99]))
    table = [{"threshold": f"{t:.2g}" + (" (benign p99)" if t == p99 else ""), "_t": t,
              "block_rate_attacks": mean([float(s >= t) for s in sa]),
              "false_positive_rate_benign": mean([float(s >= t) for s in benign])} for t in thresholds]
    ok = [r for r in table if r["false_positive_rate_benign"] <= 0.01]
    suggested = min(ok, key=lambda r: r["_t"])["_t"] if ok else None
    for r in table:
        r.pop("_t")
    out = {"n_attacks": len(sa), "n_benign": len(benign),
           "auroc": float(roc_auc_score([1] * len(sa) + [0] * len(benign), sa + benign)),
           "suggested_threshold_fpr_le_1pct": suggested, "sweep": table,
           "latency_ms_p50": percentile(lat, 50), "latency_ms_p95": percentile(lat, 95)}
    (results_dir() / "injection_guard.json").write_text(json.dumps(out, indent=2))
    md = (f"# Injection guard (Prompt Guard 2)\n\nAUROC {out['auroc']:.3f}; {len(sa)} attacks, {len(benign)} benign prompts; "
          f"latency p50 {out['latency_ms_p50']:.0f} ms, p95 {out['latency_ms_p95']:.0f} ms. Benign prompts include the golden questions used to pick the threshold, so recall at the chosen threshold is optimistic.\n\n" + md_table(table))
    (results_dir() / "injection_guard.md").write_text(md)
    print(md, f"\nSuggested threshold (benign FPR <= 1%): {suggested}")


if __name__ == "__main__":
    main()
