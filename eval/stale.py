"""End-to-end stale-answer rate on version traps, with and without the is_latest filter (k=5, retrieval mode from config).

Stale answer = the answer is judged incorrect AND cites at least one chunk from an outdated release.
Run:  python -m eval.stale
"""
from __future__ import annotations

import json

from tqdm import tqdm

from common.config import cfg, results_dir
from common.llm import LLM, QuotaExhausted
from eval.golden import load_golden
from eval.judge import judge_correct
from eval.runner import answer_one
from retrieve.search import Retriever


def main() -> None:
    traps = [q for q in load_golden() if q["type"] == "version_trap"]
    R, gen, judge = Retriever(), LLM("generator"), LLM("judge")
    out = {}
    try:
        for label, latest in (("without_filter", False), ("with_filter", True)):
            stale = wrong = 0
            for q in tqdm(traps, desc=label):
                r = answer_one(q, R, gen, cfg()["retrieval"]["mode"], 5, latest_only=latest)
                ok = judge_correct(judge, q["question"], q["reference_answer"], r["answer"], q["type"])
                wrong += not ok
                stale += (not ok) and r["cited_stale"]
            out[label] = {"n": len(traps), "stale_answer_rate": stale / len(traps), "incorrect_rate": wrong / len(traps)}
    except QuotaExhausted as e:
        print("Daily quota reached; re-run tomorrow.", str(e)[:120])
    (results_dir() / "stale_answers.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
