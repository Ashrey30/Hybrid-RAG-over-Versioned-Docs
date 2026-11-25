"""Fetch the 1M x 768-d benchmark files and spot-check the supplied ground truth with brute force.

Dataset: YoKONCy/Cohere-1M-wikipedia-768d (raw binary: cohere_train.f32, cohere_test.f32, cohere_groundtruth.i32;
vectors are L2-normalised, ground truth is exact top-1000 by cosine). ~3 GB download, read via memory-map.

Run: python -m bench.prepare_data
"""
from __future__ import annotations

import json

import numpy as np
from huggingface_hub import hf_hub_download

from common.config import ROOT, cfg, results_dir

REPO = "YoKONCy/Cohere-1M-wikipedia-768d"


def brute_force(base: np.ndarray, Q: np.ndarray, k: int = 10, block: int = 100_000, metric: str = "cosine") -> np.ndarray:
    """Exact top-k scanning the base in blocks. metric: cosine | ip (dot product) | l2 (Euclidean)."""
    Qm = Q / np.linalg.norm(Q, axis=1, keepdims=True) if metric == "cosine" else Q
    best_s = np.full((len(Q), k), -np.inf, dtype=np.float32)
    best_i = np.zeros((len(Q), k), dtype=np.int64)
    for off in range(0, len(base), block):
        B = np.asarray(base[off : off + block])
        if metric == "cosine":
            B = B / np.linalg.norm(B, axis=1, keepdims=True)
        s = Qm @ B.T
        if metric == "l2":                      # argmax of 2q.b - |b|^2 == argmin of |q-b|^2
            s = 2 * s - (B * B).sum(1)[None, :]
        kk = min(k, s.shape[1])
        idx = np.argpartition(-s, kk - 1, axis=1)[:, :kk]
        cs = np.take_along_axis(s, idx, 1)
        all_s = np.concatenate([best_s, cs], 1)
        all_i = np.concatenate([best_i, idx + off], 1)
        top = np.argsort(-all_s, 1)[:, :k]
        best_s, best_i = np.take_along_axis(all_s, top, 1), np.take_along_axis(all_i, top, 1)
    return best_i


def main() -> None:
    b = cfg()["bench"]
    dim, nq = b["dim"], b["n_queries"]
    out = ROOT / b["dir"]
    out.mkdir(parents=True, exist_ok=True)

    train = hf_hub_download(REPO, "cohere_train.f32", repo_type="dataset")
    test = hf_hub_download(REPO, "cohere_test.f32", repo_type="dataset")
    gtf = hf_hub_download(REPO, "cohere_groundtruth.i32", repo_type="dataset")

    base = np.memmap(train, dtype=np.float32, mode="r").reshape(-1, dim)
    Q = np.fromfile(test, dtype=np.float32).reshape(-1, dim)[:nq]
    gt = np.fromfile(gtf, dtype=np.int32).reshape(1000, -1)[: len(Q), :10]
    print(f"base {base.shape}, queries {Q.shape}, ground truth {gt.shape}")

    overlaps = {}
    for m in ("cosine", "ip", "l2"):           # which metric did the supplied ground truth use?
        spot = brute_force(base, Q[:100], metric=m)
        overlaps[m] = float(np.mean([len(set(a) & set(g)) / 10 for a, g in zip(spot, gt[:100])]))
        print(f"{m}: overlap with supplied ground truth = {overlaps[m]:.3f}")
    metric = max(overlaps, key=overlaps.get)
    overlap = overlaps[metric]
    report = {
        "n_vectors": int(len(base)), "n_queries": int(len(Q)),
        "mean_base_norm_first_1000": float(np.linalg.norm(base[:1000], axis=1).mean()),
        "mean_query_norm": float(np.linalg.norm(Q, axis=1).mean()),
        "metric_matching_ground_truth": metric,
        "overlap_by_metric_100q": overlaps,
        "supplied_gt_vs_bruteforce_overlap_100q": overlap,
    }
    np.save(out / "queries.npy", Q)
    np.save(out / "gt.npy", gt.astype(np.int64))
    (out / "meta.json").write_text(json.dumps({"base_path": train, "dim": dim, "metric": metric}))
    (results_dir() / "bench_data_check.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if overlap < 0.98:
        print("WARNING: supplied ground truth disagrees with brute force; investigate before benchmarking.")


if __name__ == "__main__":
    main()
