"""Evaluate the corrected router end to end without overwriting the existing final run.

Run: python -m eval.router_final_eval
Optional faithfulness scoring: python -m eval.router_final_eval --faithfulness
"""
from __future__ import annotations

import argparse

from tqdm import tqdm

from common.config import cfg, results_dir
from common.embed import embed_query
from common.io import append_jsonl, md_table, read_jsonl, write_jsonl
from common.llm import LLM, QuotaExhausted
from eval.final_eval import faithfulness, summarize
from eval.golden import load_golden
from eval.judge import judge_correct
from eval.runner import answer_one
from retrieve.router import Router
from retrieve.search import Retriever

MODE = cfg()["retrieval"]["mode"]
OUTPUT_NAME = "final_full_router_v2.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/router_v2.joblib")
    ap.add_argument("--faithfulness", action="store_true")
    args = ap.parse_args()

    qs = load_golden()
    path = results_dir() / OUTPUT_NAME
    recs = read_jsonl(path)
    done = {r["id"] for r in recs}
    router, retriever = Router.load(args.model), Retriever()
    generator, judge = LLM("generator"), LLM("judge")

    try:
        for q in tqdm([q for q in qs if q["id"] not in done], desc="full_router_v2"):
            k = router.predict_k(embed_query(q["question"]))
            r = answer_one(q, retriever, generator, MODE, k, latest_only=True)
            r["question"] = q["question"]
            r["correct"] = judge_correct(judge, q["question"], q["reference_answer"], r["answer"], q["type"])
            r["router_model"] = args.model
            append_jsonl(path, r)
            recs.append(r)
    except QuotaExhausted as e:
        print("Daily quota reached; rerun this command to resume.", str(e)[:120])

    if args.faithfulness:
        faithfulness(recs, path)
    write_jsonl(path, recs)

    rows = []
    for name in ("baseline", "hybrid_k5"):
        existing = results_dir() / f"final_{name}.jsonl"
        if not existing.exists():
            raise SystemExit(f"Required comparison results are missing: {existing}")
        rows.append(summarize(name, read_jsonl(existing)))
    rows.append(summarize("full_router_v2", recs))

    report = "# Corrected-router final evaluation\n\n" + md_table(rows)
    report += (
        f"\nRouter model: `{args.model}`\n"
        f"Router output: `{OUTPUT_NAME}`\n"
        "\nThe baseline and hybrid rows reuse the corrected results from `final_eval.md`. "
        "The router row is generated separately with the corrected-label router model.\n"
    )
    report_path = results_dir() / "final_eval_router_v2.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
