"""Baseline: dense search only, k=5, no version filter. Writes results/baseline.{jsonl,md}.

Resumable: if the daily token cap is hit it stops cleanly; re-run tomorrow (the SQLite cache keeps finished calls).
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from tqdm import tqdm

from common.config import results_dir
from common.io import md_table, write_jsonl
from common.llm import LLM, QuotaExhausted
from eval.golden import load_golden
from eval.judge import judge_correct
from eval.metrics import mean
from eval.runner import answer_one
from retrieve.search import Retriever


def summarize(records: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in records:
        by[r["type"]].append(r)
        by["ALL"].append(r)
    rows = []
    for t, rs in by.items():
        g = [r for r in rs if "recall" in r]
        rows.append({"type": t, "n": len(rs),
                     "recall@5": mean([r["recall"] for r in g]) if g else "",
                     "ndcg@5": mean([r["ndcg"] for r in g]) if g else "",
                     "correctness": mean([float(r["correct"]) for r in rs if "correct" in r])})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    qs = load_golden()[: a.limit or None]
    retriever, gen, judge = Retriever(), LLM("generator"), LLM("judge")
    records = []
    try:
        for q in tqdm(qs):
            rec = answer_one(q, retriever, gen, "dense", 5, latest_only=False)
            rec["correct"] = judge_correct(judge, q["question"], q["reference_answer"], rec["answer"], q["type"])
            records.append(rec)
    except QuotaExhausted as e:
        print(f"\nDaily quota reached after {len(records)}/{len(qs)} questions. Re-run tomorrow.\n{str(e)[:160]}")
    write_jsonl(results_dir() / "baseline.jsonl", records)
    table = md_table(summarize(records))
    (results_dir() / "baseline.md").write_text("# Baseline (dense only, k=5)\n\n" + table)
    print(table)


if __name__ == "__main__":
    main()
