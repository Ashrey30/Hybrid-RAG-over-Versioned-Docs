"""k-sweep: answer every golden question at k = 0, 2, 5, 10 with the best retrieval setup, judge each answer.

480 generations (~3 days of free quota). Fully resumable: finished (question, k) pairs are skipped,
and a daily-quota error ends the run cleanly. Leave it running / re-run each day.

Run:  python -m eval.ksweep [--mode hybrid_rerank]
"""
from __future__ import annotations

import argparse

from tqdm import tqdm

from common.config import cfg, results_dir
from common.io import append_jsonl, read_jsonl
from common.llm import LLM, QuotaExhausted
from eval.golden import load_golden
from eval.judge import judge_correct
from eval.runner import answer_one
from retrieve.search import Retriever


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=cfg()["retrieval"]["mode"])
    ap.add_argument("--ks", default="0,2,5,10")
    a = ap.parse_args()
    ks = [int(x) for x in a.ks.split(",")]
    path = results_dir() / "ksweep.jsonl"
    done = {(r["id"], r["k"]) for r in read_jsonl(path)}
    qs = load_golden()
    todo = [(q, k) for q in qs for k in ks if (q["id"], k) not in done]
    print(f"{len(done)} done, {len(todo)} to go")
    R, gen, judge = Retriever(), LLM("generator"), LLM("judge")
    try:
        for q, k in tqdm(todo):
            rec = answer_one(q, R, gen, a.mode, k, latest_only=True)
            rec["correct"] = judge_correct(judge, q["question"], q["reference_answer"], rec["answer"], q["type"])
            rec.pop("contexts", None)
            append_jsonl(path, rec)
    except QuotaExhausted as e:
        print(f"\nDaily quota reached. Progress is saved; re-run tomorrow.\n{str(e)[:160]}")


if __name__ == "__main__":
    main()
