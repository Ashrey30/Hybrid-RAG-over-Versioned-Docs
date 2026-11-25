"""Recall-vs-p95 plot (one line per quantization mode), memory table, and two candidate recommended settings.
Run: python -m bench.plots
"""
from __future__ import annotations

import pandas as pd

from common.config import results_dir
from common.io import md_table

R = results_dir()
COLS = ["m", "mode", "ef", "recall10", "p50_ms", "p95_ms", "ram_mb", "disk_mb"]


def capped_report() -> None:
    """Compare the 2 GB-capped run (originals on disk) with the unconstrained run at m=16."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cp = R / "bench_capped.csv"
    if not cp.exists():
        return
    free = pd.read_csv(R / "bench_results.csv")
    free = free[free.m == 16]
    cap = pd.read_csv(cp)
    j = free.merge(cap, on=["mode", "ef"], suffixes=("_free", "_cap"))
    rows = [{"mode": r["mode"], "ef": int(r["ef"]), "recall_free": r["recall10_free"], "recall_capped": r["recall10_cap"],
             "p95_free_ms": r["p95_ms_free"], "p95_capped_ms": r["p95_ms_cap"],
             "slowdown": r["p95_ms_cap"] / r["p95_ms_free"], "ram_capped_mb": int(r["ram_mb_cap"])} for _, r in j.iterrows()]
    md = ("# 2 GB memory cap vs unconstrained (m=16)\n\nCapped run: original vectors on disk, quantized copies in RAM, "
          "container limited to 2 GB. Latency is Qdrant's server-side search time. `ram_capped_mb` is from `docker stats`, "
          "which excludes page cache, so float32 (read from disk) looks small; compare it with the in-RAM size of each "
          "representation (float32 about 3,000 MB, int8 about 770 MB, binary about 100 MB).\n\n" + md_table(rows))
    (R / "bench_capped.md").write_text(md)
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for mode, g in j.groupby("mode"):
        g = g.sort_values("ef")
        line, = ax.plot(g.ef, g.p95_ms_free, marker="o", label=f"{mode} (no cap)")
        ax.plot(g.ef, g.p95_ms_cap, marker="s", linestyle="--", color=line.get_color(), label=f"{mode} (2 GB cap)")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("search ef")
    ax.set_ylabel("p95 server-side latency (ms)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(R / "bench_capped_vs_free.png", dpi=150)
    print(md)


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(R / "bench_results.csv")
    ms = sorted(df.m.unique())
    fig, axes = plt.subplots(1, len(ms), figsize=(4.2 * len(ms), 4), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], ms):
        for mode, g in df[df.m == m].groupby("mode"):
            g = g.sort_values("ef")
            ax.plot(g.p95_ms, g.recall10, marker="o", label=mode)
        ax.set_title(f"m = {m}")
        ax.set_xlabel("p95 server-side search latency (ms)")
    axes[0][0].set_ylabel("recall@10 vs exact")
    axes[0][0].legend()
    fig.tight_layout()
    fig.savefig(R / "bench_recall_vs_p95.png", dpi=150)

    mem = df.groupby(["m", "mode"]).agg(ram_mb=("ram_mb", "max"), disk_mb=("disk_mb", "max"),
                                         graph_build_s=("graph_build_s", "first"), quant_build_s=("quant_build_s", "first")).reset_index()
    ok = df[df.recall10 >= 0.95]
    cands = []
    if len(ok):
        for name, order in (("lowest RAM", ["ram_mb", "p95_ms"]), ("lowest p95", ["p95_ms", "ram_mb"])):
            row = ok.sort_values(order).iloc[0]
            cands.append({"criterion": name, **{c: row[c] for c in COLS}})
    md = ("# Memory, disk and build time\n\n" + md_table(mem.to_dict("records"))
          + "\n## Candidate settings (recall@10 >= 0.95)\n\n"
          + (md_table(cands) if cands else "No setting reached 0.95 recall@10; pick one by hand.\n")
          + "\nLatency is Qdrant's server-side search time. Write the reason for your recommendation yourself in the README.\n")
    (R / "bench_memory.md").write_text(md)
    print(md)
    capped_report()


if __name__ == "__main__":
    main()
