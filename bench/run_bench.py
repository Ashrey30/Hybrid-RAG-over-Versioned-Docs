"""HNSW + quantization benchmark: m in {8,16,32} x {float32, scalar int8, binary} x ef in {32,64,128,256} = 36 points.

Per point: recall@10 vs exact search (1,000 queries), p50/p95 server-side search latency after 100 warm-ups (median of 3 repeats), RAM, build time, disk.
Run plugged in, other apps closed.  Resumable: finished rows in results/bench_results.csv are skipped.

  python -m bench.run_bench                 # normal run, Qdrant on :6333 (container 'qdrant')
  python -m bench.run_bench --capped        # 2 GB container on :6335 (container 'qdrant-capped'), m=16, originals on disk
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import time

import httpx
import numpy as np
from qdrant_client import QdrantClient, models

from common.config import ROOT, cfg, results_dir

M_VALUES = [8, 16, 32]
EF_VALUES = [32, 64, 128, 256]
EF_CONSTRUCT = 128
MODES = ["float32", "scalar", "binary"]
FIELDS = ["capped", "m", "mode", "ef", "recall10", "p50_ms", "p95_ms", "client_p50_ms", "client_p95_ms", "ram_mb", "disk_mb", "graph_build_s", "quant_build_s"]


def quant_config(mode: str):
    if mode == "scalar":
        return models.ScalarQuantization(scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, quantile=0.99, always_ram=True))
    if mode == "binary":
        return models.BinaryQuantization(binary=models.BinaryQuantizationConfig(always_ram=True))
    return None


def search_params(mode: str, ef: int) -> models.SearchParams:
    if mode == "binary":
        q = models.QuantizationSearchParams(rescore=True, oversampling=3.0)
    elif mode == "scalar":
        q = models.QuantizationSearchParams(rescore=True, oversampling=1.0)
    else:
        q = None
    return models.SearchParams(hnsw_ef=ef, quantization=q)


def wait_green(client: QdrantClient, name: str) -> None:
    while True:
        info = client.get_collection(name)
        if info.status == models.CollectionStatus.GREEN and info.optimizer_status == models.OptimizersStatusOneOf.OK:
            return
        time.sleep(2)


def container_ram_mb(container: str) -> float:
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container], capture_output=True, text=True).stdout
    used = out.split("/")[0].strip()
    num = float("".join(c for c in used if c.isdigit() or c == "."))
    return num * (1024 if "GiB" in used else 1 if "MiB" in used else 1 / 1024)


def disk_mb(container: str, name: str) -> float:
    out = subprocess.run(["docker", "exec", container, "du", "-sm", f"/qdrant/storage/collections/{name}"], capture_output=True, text=True).stdout
    return float(out.split()[0]) if out else float("nan")


DISTANCE = {"cosine": models.Distance.COSINE, "ip": models.Distance.DOT, "l2": models.Distance.EUCLID}


def build_graph(client: QdrantClient, name: str, base: np.ndarray, m: int, on_disk: bool, metric: str = "cosine") -> float:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        name,
        vectors_config=models.VectorParams(size=base.shape[1], distance=DISTANCE[metric], on_disk=on_disk),
        hnsw_config=models.HnswConfigDiff(m=m, ef_construct=EF_CONSTRUCT),
        optimizers_config=models.OptimizersConfigDiff(indexing_threshold=20000),
    )
    t0 = time.perf_counter()
    client.upload_collection(name, vectors=base, ids=range(len(base)), batch_size=256, parallel=1)
    wait_green(client, name)
    n = client.count(name, exact=True).count
    info = client.get_collection(name)
    print(f"{name}: {n} points, {info.indexed_vectors_count} indexed vectors")
    if n != len(base):
        raise RuntimeError(f"{name} holds {n} points but {len(base)} were uploaded: the upload was incomplete. "
                           "Check `docker inspect <container> --format '{{.State.OOMKilled}}'`; raise the memory cap if it was OOM-killed.")
    return time.perf_counter() - t0


def sanity_exact(http: httpx.Client, name: str, Q, gt, n: int = 20) -> None:
    """Exact (brute-force) search inside Qdrant on a few queries: if this disagrees with the ground truth,
    the stored vectors or IDs are wrong; if it agrees, any low recall afterwards comes from the HNSW index."""
    hits = 0
    for q, g in zip(Q[:n], gt[:n]):
        r = http.post(f"/collections/{name}/points/query", json={"query": q.tolist(), "limit": 10, "params": {"exact": True}})
        r.raise_for_status()
        hits += len({p["id"] for p in r.json()["result"]["points"]} & set(g.tolist()))
    rec = hits / (10 * n)
    print(f"{name}: exact-search recall on {n} queries = {rec:.3f} (should be about 1.0)")
    if rec < 0.98:
        raise RuntimeError(f"{name}: exact search disagrees with the ground truth ({rec:.3f}); the stored vectors or IDs are wrong")


def _body(q, mode: str, ef: int) -> dict:
    params: dict = {"hnsw_ef": ef}
    if mode == "binary":
        params["quantization"] = {"rescore": True, "oversampling": 3.0}
    elif mode == "scalar":
        params["quantization"] = {"rescore": True, "oversampling": 1.0}
    return {"query": q.tolist(), "limit": 10, "params": params}


def measure(http: httpx.Client, name: str, Q, gt, mode: str, ef: int, repeats: int = 3):
    """Latency = Qdrant's own server-side search time (the `time` field of each response), because client-side
    timings through Docker Desktop on Windows are quantised by the ~15.6 ms OS timer tick.
    Client-side p50/p95 are kept as extra columns for transparency."""
    url = f"/collections/{name}/points/query"
    for q in Q[:100]:   # warm-up
        http.post(url, json=_body(q, mode, ef)).raise_for_status()
    s50, s95, c50, c95, recall = [], [], [], [], 0.0
    for rep in range(repeats):
        srv, cli, hits = [], [], 0
        for q, g in zip(Q, gt):
            t0 = time.perf_counter()
            r = http.post(url, json=_body(q, mode, ef))
            cli.append((time.perf_counter() - t0) * 1000)
            r.raise_for_status()
            j = r.json()
            srv.append(j["time"] * 1000)
            if rep == 0:
                hits += len({p["id"] for p in j["result"]["points"]} & set(g.tolist()))
        if rep == 0:
            recall = hits / (10 * len(Q))
        s50.append(float(np.percentile(srv, 50)))
        s95.append(float(np.percentile(srv, 95)))
        c50.append(float(np.percentile(cli, 50)))
        c95.append(float(np.percentile(cli, 95)))
    return recall, statistics.median(s50), statistics.median(s95), statistics.median(c50), statistics.median(c95)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capped", action="store_true")
    ap.add_argument("--build-only", action="store_true", help="build and verify the collection for the capped run in the NORMAL container, keep it, and exit")
    ap.add_argument("--on-disk", action="store_true", help="store original vectors on disk even without the memory cap (diagnostic)")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: first N vectors, 100 queries, m=8 only, 1 repeat; writes bench_smoke.csv")
    a = ap.parse_args()
    d = ROOT / cfg()["bench"]["dir"]
    meta = json.loads((d / "meta.json").read_text())
    base = np.memmap(meta["base_path"], dtype=np.float32, mode="r").reshape(-1, meta["dim"])
    Q, gt = np.load(d / "queries.npy"), np.load(d / "gt.npy")
    if a.limit:
        from bench.prepare_data import brute_force

        base, Q = base[: a.limit], Q[:100]
        gt = brute_force(base, Q, 10, metric=meta.get("metric", "cosine"))   # exact neighbours within the subset
    port, container = (6335, "qdrant-capped") if a.capped else (6333, "qdrant")
    client = QdrantClient(host="localhost", port=port, timeout=600, check_compatibility=False)
    http = httpx.Client(base_url=f"http://localhost:{port}", timeout=120)
    path = results_dir() / ("bench_smoke.csv" if a.limit else "bench_capped.csv" if a.capped else "bench_results.csv")
    done = set()
    if path.exists():
        with open(path) as f:
            done = {(r["m"], r["mode"], r["ef"]) for r in csv.DictReader(f)}
    else:
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, FIELDS).writeheader()

    capped_like = a.capped or a.build_only
    for m in ([8] if a.limit else [16] if capped_like else M_VALUES):
        name = f"bench_m{m}{'_capped' if capped_like else ''}"
        todo_modes = [md for md in MODES if any((str(m), md, str(ef)) not in done for ef in EF_VALUES)]
        if not todo_modes and not a.build_only:
            continue
        if a.capped:   # serve the collection that --build-only created and verified in the normal container
            if not client.collection_exists(name):
                raise SystemExit(f"{name} not found on the capped container. Run `python -m bench.run_bench --build-only` first, "
                                 "then stop qdrant and start qdrant-capped (they share one storage volume).")
            graph_s = -1.0   # -1 = built in the normal container, not under the cap
            print(f"{name}: {client.count(name, exact=True).count} points")
            try:   # start from plain float32 even if an earlier run left quantization switched on
                client.update_collection(name, quantization_config=models.Disabled.DISABLED)
                time.sleep(3)
                wait_green(client, name)
            except Exception as e:  # noqa: BLE001
                print("could not reset quantization:", str(e)[:100])
        else:
            graph_s = build_graph(client, name, base, m, on_disk=a.build_only or a.on_disk, metric=meta.get("metric", "cosine"))
        sanity_exact(http, name, Q, gt)
        if a.build_only:
            print(f"{name} built and verified (exact recall ok). Now: docker compose stop qdrant; "
                  "docker compose -f docker-compose.bench-capped.yml up -d; python -m bench.run_bench --capped")
            return
        for mode in MODES:                      # quantization is switched on the same graph (HNSW is kept)
            q_s = 0.0
            if mode != "float32":
                t0 = time.perf_counter()
                client.update_collection(name, quantization_config=quant_config(mode))
                time.sleep(3)
                wait_green(client, name)
                q_s = time.perf_counter() - t0
            if mode not in todo_modes:
                continue
            for ef in EF_VALUES:
                if (str(m), mode, str(ef)) in done:
                    continue
                recall, p50, p95, c50, c95 = measure(http, name, Q, gt, mode, ef, repeats=1 if a.limit else 3)
                row = {"capped": int(a.capped), "m": m, "mode": mode, "ef": ef, "recall10": round(recall, 4),
                       "p50_ms": round(p50, 2), "p95_ms": round(p95, 2),
                       "client_p50_ms": round(c50, 2), "client_p95_ms": round(c95, 2), "ram_mb": round(container_ram_mb(container)),
                       "disk_mb": round(disk_mb(container, name)), "graph_build_s": round(graph_s), "quant_build_s": round(q_s)}
                with open(path, "a", newline="") as f:
                    csv.DictWriter(f, FIELDS).writerow(row)
                print(row)
        if not a.capped:
            client.delete_collection(name)


if __name__ == "__main__":
    main()
