"""Label questions from the k-sweep, train the router (5-fold CV), compare six policies, save the model.

Run:  python -m eval.router_eval
"""
from __future__ import annotations

import argparse
import time

import joblib
import numpy as np

from common.config import ROOT, cfg, results_dir
from common.embed import embed_queries
from common.io import md_table, read_jsonl
from eval.golden import load_golden
from eval.metrics import mean, percentile
from retrieve.router import KS, choose_k, label_min_k


def bootstrap_ci(x: np.ndarray, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix-unanswerable", action="store_true",
                    help="unanswerable questions need retrieval to discover the docs lack an answer, so they cannot be labelled k=0")
    args = ap.parse_args()
    sfx = "_v2" if args.fix_unanswerable else ""

    def ks_for(q: dict) -> list:
        return [k for k in KS if not (args.fix_unanswerable and q["type"] == "unanswerable" and k == 0)]

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    sweep = read_jsonl(results_dir() / "ksweep.jsonl")
    rec = {(r["id"], r["k"]): r for r in sweep}
    qs = [q for q in sorted(load_golden(), key=lambda q: q["id"]) if all((q["id"], k) in rec for k in KS)]
    print(f"{len(qs)} questions have all {len(KS)} k-values")
    labels = np.array([label_min_k({k: rec[(q["id"], k)]["correct"] for k in ks_for(q)}) for q in qs])
    print("label counts:", dict(zip(*np.unique(labels, return_counts=True))))
    X = embed_queries([q["question"] for q in qs])

    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    n_splits = min(5, int(np.bincount(np.searchsorted(np.unique(labels), labels)).min()))
    if n_splits < 2:
        raise SystemExit("A class has <2 examples; merge or drop that k value (see Risks and fallbacks).")
    proba = cross_val_predict(clf, X, labels, cv=StratifiedKFold(n_splits, shuffle=True, random_state=0), method="predict_proba")
    classes = np.unique(labels)
    min_conf = cfg()["router"]["min_confidence"]
    router_k = np.array([choose_k(p, classes, min_conf) for p in proba])

    def stats(name: str, chosen: np.ndarray, overhead_ms: float = 0.0) -> dict:
        rs = [rec[(q["id"], int(k))] for q, k in zip(qs, chosen)]
        corr = np.array([float(r["correct"]) for r in rs])
        lat = [r["retrieve_ms"] + r["gen_latency_ms"] + overhead_ms for r in rs]
        lo, hi = bootstrap_ci(corr)
        return {"policy": name, "accuracy": corr.mean(), "ci_low": lo, "ci_high": hi,
                "mean_tokens": mean([r["tokens"] for r in rs]), "p95_latency_ms": percentile(lat, 95)}

    # router overhead: classifier only, and including the query embedding
    clf.fit(X, labels)
    t0 = time.perf_counter()
    for _ in range(200):
        clf.predict_proba(X[:1])
    clf_ms = (time.perf_counter() - t0) / 200 * 1000
    t0 = time.perf_counter()
    embed_queries([qs[0]["question"]])
    emb_ms = (time.perf_counter() - t0) * 1000

    n = len(qs)
    rows = [stats(f"fixed k={k}" if k else "never retrieve", np.full(n, k)) for k in (0, 2, 5, 10)]
    rows.append(stats("oracle", labels))
    rows.append(stats("router", router_k, overhead_ms=clf_ms))
    out = results_dir()
    (out / f"router_policies{sfx}.md").write_text(
        "# Router vs five policies\n\n" + md_table(rows)
        + f"\nRouter overhead: classifier {clf_ms:.2f} ms; query embedding {emb_ms:.1f} ms (the embedding is reused by retrieval and the cache).\n"
        + f"\nLabel counts: { {int(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))} }\n")
    print(md_table(rows), f"\nrouter overhead {clf_ms:.2f} ms (+ embedding {emb_ms:.1f} ms)")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    for r in rows:
        ax.scatter(r["mean_tokens"], r["accuracy"])
        ax.annotate(r["policy"], (r["mean_tokens"], r["accuracy"]), textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax.set_xlabel("mean tokens per query")
    ax.set_ylabel("answer accuracy")
    ax.set_title("Accuracy vs cost, one point per policy")
    fig.tight_layout()
    fig.savefig(out / f"router_plot{sfx}.png", dpi=150)

    model_path = "models/router_v2.joblib" if sfx else cfg()["router"]["path"]
    joblib.dump(clf, ROOT / model_path)
    print("saved", model_path)


if __name__ == "__main__":
    main()
