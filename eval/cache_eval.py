"""Semantic cache evaluation: paraphrase pairs vs near-miss pairs, stage by stage.

Splits in data/cache_pairs.jsonl:  dev (first 26, rules were tuned on them), heldout (15, seen once: now development
data too) and fresh (generated from random documentation passages; the TEST set, rules and thresholds frozen first).

  python -m eval.cache_eval --fresh 40            # LLM writes fresh pairs from random passages (split=fresh)
  python -m eval.cache_eval --review --split fresh    # print them, numbered
  python -m eval.cache_eval --drop 3 7 --split fresh  # delete bad near-misses by those numbers
  python -m eval.cache_eval --split development   # calibrate the verifier threshold on dev + heldout pairs
  python -m eval.cache_eval --split fresh         # final, untouched test

Stages: (1) similarity, (2) + entity guard, (3) + retrieval consistency, (4) + learned duplicate verifier.
The exact-match tier is not swept (it can only return the identical question).
"""
from __future__ import annotations

import argparse
import random
import time

import numpy as np

from common.config import cfg, data_dir, results_dir
from common.embed import embed_queries
from common.io import md_table, read_jsonl, write_jsonl
from common.llm import LLM, json_from_text
from eval.golden import NEEDS_RETRIEVAL, load_golden
from guard.match import entities_compatible

SYS = "You write test questions for a semantic cache. Reply with JSON only."
THRESHOLDS = [0.80, 0.84, 0.86, 0.88, 0.90, 0.92, 0.94, 0.96]
VERIFY_THRESHOLDS = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
RULES = ("The near-miss must copy the question and change exactly ONE thing (an entity, value, version, scope, option "
         "or the opposite condition) so that the correct answer is a different fact. It must stay a sensible question "
         "about real Kubernetes concepts, with no false premise.")
PROMPT = ("Original question: {q}\n\nWrite (1) a paraphrase that asks exactly the same thing in different words, and "
          "(2) a near-miss. " + RULES + ' Reply as JSON: {{"paraphrase": "...", "near_miss": "..."}}')
FRESH_PROMPT = ("Passage:\n{text}\n\nWrite (1) one specific question answerable from this passage alone, (2) a paraphrase "
                "of it that asks exactly the same thing in different words, and (3) a near-miss. " + RULES +
                ' Reply as JSON: {{"question": "...", "paraphrase": "...", "near_miss": "..."}}')


def in_split(r: dict, split: str) -> bool:
    s = r.get("split", "dev")
    return split == "all" or s == split or (split == "development" and s in ("dev", "heldout"))


def make(add: int = 0) -> None:
    """Older helper: pairs from unused golden questions (tagged heldout when --add is used)."""
    path = data_dir() / "cache_pairs.jsonl"
    rows = read_jsonl(path) if add else []
    seen = {r["question"] for r in rows}
    random.seed(11 if add else 3)
    pool = [q for q in load_golden() if q["type"] in NEEDS_RETRIEVAL and q["question"] not in seen]
    llm = LLM("judge")
    new = 0
    for q in random.sample(pool, min(add or 30, len(pool))):
        j = json_from_text(llm.generate(PROMPT.format(q=q["question"]), system=SYS).text)
        if j and j.get("paraphrase") and j.get("near_miss"):
            row = {"question": q["question"], "paraphrase": j["paraphrase"], "near_miss": j["near_miss"]}
            if add:
                row["split"] = "heldout"
            rows.append(row)
            new += 1
    write_jsonl(path, rows)
    print(f"added {new} pairs ({len(rows)} total) in data/cache_pairs.jsonl - review the near-misses by hand")


def make_fresh(n: int) -> None:
    """Test pairs from random documentation passages (not golden questions): unlimited, and unseen."""
    path = data_dir() / "cache_pairs.jsonl"
    rows = read_jsonl(path)
    used = {r.get("chunk_id") for r in rows if r.get("chunk_id")}
    random.seed(21)
    pool = [c for c in read_jsonl(data_dir() / "chunks.jsonl") if c["is_latest"] and c["tokens"] >= 80 and c["chunk_id"] not in used]
    llm = LLM("judge")
    new = 0
    for c in random.sample(pool, min(n, len(pool))):
        j = json_from_text(llm.generate(FRESH_PROMPT.format(text=c["text"]), system=SYS).text)
        if j and j.get("question") and j.get("paraphrase") and j.get("near_miss"):
            rows.append({"question": j["question"], "paraphrase": j["paraphrase"], "near_miss": j["near_miss"],
                         "split": "fresh", "chunk_id": c["chunk_id"]})
            new += 1
    write_jsonl(path, rows)
    print(f"added {new} fresh pairs. Next: python -m eval.cache_eval --review --split fresh")


def positions(rows: list, split: str) -> list:
    return [i for i, r in enumerate(rows) if in_split(r, split)]


def review(split: str) -> None:
    rows = read_jsonl(data_dir() / "cache_pairs.jsonl")
    for n, i in enumerate(positions(rows, split)):
        r = rows[i]
        print(f"[{n}] ORIGINAL : {r['question']}\n    PARAPHRASE: {r['paraphrase']}\n    NEAR-MISS : {r['near_miss']}\n")
    print("Delete a pair if the near-miss would have the SAME answer as the original, or does not make sense:")
    print(f"  python -m eval.cache_eval --drop <numbers> --split {split}")


def drop(numbers: list, split: str) -> None:
    path = data_dir() / "cache_pairs.jsonl"
    rows = read_jsonl(path)
    pos = positions(rows, split)
    gone = {pos[n] for n in numbers if 0 <= n < len(pos)}
    write_jsonl(path, [r for i, r in enumerate(rows) if i not in gone])
    print(f"dropped {len(gone)} pairs; {len(pos) - len(gone)} remain in split={split}")


def sweep(split: str = "all") -> None:
    from qdrant_client import QdrantClient

    from guard.cache import SemanticCache
    from retrieve.search import Retriever

    rows = [r for r in read_jsonl(data_dir() / "cache_pairs.jsonl") if in_split(r, split)]
    if not rows:
        raise SystemExit(f"no pairs in split={split}")
    Q = embed_queries([r["question"] for r in rows])
    P = embed_queries([r["paraphrase"] for r in rows])
    N = embed_queries([r["near_miss"] for r in rows])
    sim_p, sim_n = (Q * P).sum(1), (Q * N).sum(1)

    gold_id = {q["question"]: q["id"] for q in load_golden()}
    sweep_recs = {(r["id"], r["k"]): r for r in read_jsonl(results_dir() / "ksweep.jsonl")}
    R, mode = Retriever(), cfg()["retrieval"]["mode"]
    c = cfg()["cache"]
    min_ov, t0_cfg, v0 = c.get("min_cited_overlap", 0.5), c["threshold"], c.get("verify_threshold", 0.5)
    ent_p = np.array([entities_compatible(r["paraphrase"], r["question"]) for r in rows])
    ent_n = np.array([entities_compatible(r["near_miss"], r["question"]) for r in rows])
    ret_p, ret_n, retr_ms = [], [], []
    for r in rows:
        if r.get("chunk_id"):                      # fresh pairs: the passage they were written from is the cited chunk
            cited = [r["chunk_id"]]
        else:
            rec = sweep_recs.get((gold_id.get(r["question"]), 5)) or {}
            cited = rec.get("cited_ids") or [h.chunk_id for h in R.retrieve(r["question"], mode, 5, "restricted", True).hits[:2]]

        def consistent(text: str) -> bool:
            res = R.retrieve(text, mode, 5, "restricted", True)
            retr_ms.append(res.timings_ms.get("retrieve", 0.0))
            return len({h.chunk_id for h in res.hits} & set(cited)) / len(cited) >= min_ov

        ret_p.append(consistent(r["paraphrase"]))
        ret_n.append(consistent(r["near_miss"]))
    ret_p, ret_n = np.array(ret_p), np.array(ret_n)

    ver_p = ver_n = None
    ver_ms = 0.0
    if c.get("use_verifier", True):
        from guard.verify import DuplicateVerifier

        V = DuplicateVerifier()
        V.score(rows[0]["paraphrase"], rows[0]["question"])      # warm-up
        t0 = time.perf_counter()
        ver_p = np.array(V.scores([(r["paraphrase"], r["question"]) for r in rows]))
        ver_ms = (time.perf_counter() - t0) / len(rows) * 1000 / 2     # per pair per order
        ver_n = np.array(V.scores([(r["near_miss"], r["question"]) for r in rows]))
    vp = ver_p >= v0 if ver_p is not None else np.ones(len(rows), bool)
    vn = ver_n >= v0 if ver_n is not None else np.ones(len(rows), bool)

    table = []
    for t in THRESHOLDS:
        sp, sn = sim_p >= t, sim_n >= t
        table.append({"threshold": t, "sim_hit": float(sp.mean()), "sim_false": float(sn.mean()),
                      "+entity_hit": float((sp & ent_p).mean()), "+entity_false": float((sn & ent_n).mean()),
                      "+retrieval_hit": float((sp & ent_p & ret_p).mean()), "+retrieval_false": float((sn & ent_n & ret_n).mean()),
                      "+verifier_hit": float((sp & ent_p & ret_p & vp).mean()), "+verifier_false": float((sn & ent_n & ret_n & vn).mean())})
    vtable = []
    if ver_p is not None:
        sp, sn = sim_p >= t0_cfg, sim_n >= t0_cfg
        for v in VERIFY_THRESHOLDS:
            vtable.append({"verify_threshold": v,
                           "verifier_only_hit": float((sp & (ver_p >= v)).mean()), "verifier_only_false": float((sn & (ver_n >= v)).mean()),
                           "all_stages_hit": float((sp & ent_p & ret_p & (ver_p >= v)).mean()),
                           "all_stages_false": float((sn & ent_n & ret_n & (ver_n >= v)).mean())})

    cache = SemanticCache(QdrantClient(":memory:"), threshold=0.0, version="eval")
    cache.ensure()
    for r, v in zip(rows, Q):
        cache.store(v, "public", r["question"], {"response": {}, "k": 0, "debug": {}})
    t0 = time.perf_counter()
    for v in P:
        cache.lookup(v, "public")
    lookup_ms = (time.perf_counter() - t0) / len(P) * 1000
    t0 = time.perf_counter()
    embed_queries([rows[0]["paraphrase"]])
    embed_ms = (time.perf_counter() - t0) * 1000
    full = [r["retrieve_ms"] + r["gen_latency_ms"] for r in sweep_recs.values() if r["k"] == 5]
    full_ms = sum(full) / len(full) if full else float("nan")
    verified_ms = embed_ms + lookup_ms + float(np.mean(retr_ms)) + 2 * ver_ms

    sp, sn = sim_p >= t0_cfg, sim_n >= t0_cfg
    leaks = [r["near_miss"] for r, hit in zip(rows, sn & ent_n & ret_n & vn) if hit]
    md = (f"# Semantic cache: stage-by-stage ({len(rows)} pairs, split={split})\n\n" + md_table(table)
          + (f"\n## Verifier threshold sweep (similarity threshold {t0_cfg})\n\n" + md_table(vtable) if vtable else "")
          + f"\nHit = paraphrase served; false = near-miss served (wrong answer). One pair is {100 / len(rows):.1f} points.\n"
          + f"\nVerified hit costs about {verified_ms:.0f} ms (embedding {embed_ms:.0f}, lookup {lookup_ms:.1f}, retrieval "
          + f"{float(np.mean(retr_ms)):.0f}, verifier {2 * ver_ms:.0f}) against {full_ms:.0f} ms uncached, saving about {full_ms - verified_ms:.0f} ms.\n"
          + f"\nAt the configured thresholds (similarity {t0_cfg}, verifier {v0}): hit {float((sp & ent_p & ret_p & vp).mean()):.1%}, "
          + f"false {float((sn & ent_n & ret_n & vn).mean()):.1%}.\n"
          + ("\nNear-misses still served:\n" + "\n".join(f"- {q}" for q in leaks) + "\n" if leaks else ""))
    fname = {"all": "cache_threshold.md"}.get(split, f"cache_{split}.md")
    (results_dir() / fname).write_text(encoding="utf-8", data=md)
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", action="store_true")
    ap.add_argument("--add", type=int, default=0)
    ap.add_argument("--fresh", type=int, default=0)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--drop", type=int, nargs="+")
    ap.add_argument("--split", choices=["all", "dev", "heldout", "development", "fresh"], default="all")
    a = ap.parse_args()
    if a.fresh:
        make_fresh(a.fresh)
    elif a.make or a.add:
        make(a.add)
    elif a.review:
        review(a.split)
    elif a.drop:
        drop(a.drop, a.split)
    else:
        sweep(a.split)
