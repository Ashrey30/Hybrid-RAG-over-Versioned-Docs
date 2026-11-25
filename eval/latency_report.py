"""Run the golden set through the live API and report p50/p95 per stage and in total.
Start the API first (uvicorn api.main:app). Run: python -m eval.latency_report
"""
from __future__ import annotations

import time
from collections import defaultdict

import httpx

from common.config import results_dir
from common.io import md_table
from eval.api_auth import authenticate_api
from eval.golden import load_golden
from eval.metrics import percentile

BASE = "http://localhost:8000"


def main() -> None:
    with httpx.Client(timeout=120) as c:
        authenticate_api(c, BASE, require_admin=True)
        stages, wall, hits, n = defaultdict(list), [], 0, 0
        for q in load_golden():
            t0 = time.perf_counter()
            response = c.post(f"{BASE}/ask", json={"question": q["question"]})
            response.raise_for_status()
            r = response.json()
            wall.append((time.perf_counter() - t0) * 1000)
            n += 1
            hits += r["trace"]["cache_hit"]
            for k, v in r["trace"]["timings_ms"].items():
                stages[k].append(v)
    rows = [{"stage": k, "n": len(v), "p50_ms": percentile(v, 50), "p95_ms": percentile(v, 95)} for k, v in stages.items()]
    rows.append({"stage": "wall clock (client)", "n": len(wall), "p50_ms": percentile(wall, 50), "p95_ms": percentile(wall, 95)})
    md = "# Per-stage latency through the API\n\n" + md_table(rows) + f"\nCache hit rate: {hits / max(n, 1):.2%}\n"
    (results_dir() / "latency_stages.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
