"""Final evaluation of three configurations: baseline, hybrid+rerank at fixed k=5, and the full system with the router.
Reports answer correctness, hallucination rate (RAGAS faithfulness < 1), abstention accuracy, citation hit rate.

  python -m eval.final_eval [--faithfulness]     # run faithfulness only on these final configs (saves quota)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re

from tqdm import tqdm

from common.config import cfg, results_dir
from common.embed import embed_query
from common.io import md_table, read_jsonl, write_jsonl
from common.llm import LLM, QuotaExhausted
from eval.golden import load_golden
from eval.judge import judge_correct
from eval.metrics import mean
from eval.runner import answer_one
from retrieve.router import Router
from retrieve.search import Retriever

MODE = cfg()["retrieval"]["mode"]
CONFIGS = ["baseline", "hybrid_k5", "full_router"]
STRIP = re.compile(r"\s*\[[0-9a-f]{10}(?:\s*[,;]\s*[0-9a-f]{10})*\]")


def faithfulness(records: list[dict], path) -> None:
    from langchain_openai import ChatOpenAI
    import nest_asyncio

    original_apply = nest_asyncio.apply
    nest_asyncio.apply = lambda *args, **kwargs: None
    try:
        from ragas import SingleTurnSample
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness
    finally:
        nest_asyncio.apply = original_apply

    spec = cfg()["llm"]["judge"]
    prov = cfg()["providers"][spec["provider"]]
    llm = ChatOpenAI(model=spec["model"], base_url=prov["base_url"], api_key=os.environ[prov["key_env"]], temperature=0)
    metric = Faithfulness(llm=LangchainLLMWrapper(llm))
    for r in tqdm(records, desc="faithfulness"):
        if "faith" in r or r["status"] != "answered" or not r.get("contexts"):
            continue
        sample = SingleTurnSample(user_input=r["question"], response=STRIP.sub("", r["answer"]), retrieved_contexts=r["contexts"])
        r["faith"] = float(asyncio.run(metric.single_turn_ascore(sample)))
        write_jsonl(path, records)


def summarize(name: str, recs: list[dict]) -> dict:
    ans = [r for r in recs if r["type"] == "unanswerable"]
    answerable = [r for r in recs if r["type"] != "unanswerable"]
    gold = [r for r in recs if "citation_hit" in r]
    faith = [r["faith"] for r in recs if "faith" in r]
    return {
        "config": name, "n": len(recs),
        "correctness": mean([float(r["correct"]) for r in recs if "correct" in r]),
        "hallucination_rate": mean([float(f < 1) for f in faith]) if faith else "",
        "abstention_accuracy": mean([float(r["status"] == "abstained") for r in ans]),
        "false_abstention_rate": mean([float(r["status"] == "abstained") for r in answerable]),
        "citation_hit_rate": mean([float(r["citation_hit"]) for r in gold]),
        "mean_tokens": mean([r["tokens"] for r in recs]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faithfulness", action="store_true")
    a = ap.parse_args()
    qs = load_golden()
    R, gen, judge = Retriever(), LLM("generator"), LLM("judge")
    router = Router.load()
    rows = []
    for name in CONFIGS:
        path = results_dir() / f"final_{name}.jsonl"
        recs = read_jsonl(path)
        done = {r["id"] for r in recs}
        try:
            for q in tqdm([q for q in qs if q["id"] not in done], desc=name):
                if name == "baseline":
                    r = answer_one(q, R, gen, "dense", 5, latest_only=False)
                elif name == "hybrid_k5":
                    r = answer_one(q, R, gen, MODE, 5, latest_only=True)
                else:
                    k = router.predict_k(embed_query(q["question"]))
                    r = answer_one(q, R, gen, MODE, k, latest_only=True)
                r["question"] = q["question"]
                r["correct"] = judge_correct(judge, q["question"], q["reference_answer"], r["answer"], q["type"])
                recs.append(r)
        except QuotaExhausted as e:
            print("Daily quota reached; re-run tomorrow.", str(e)[:120])
        if a.faithfulness:
            faithfulness(recs, path)
        write_jsonl(path, recs)
        rows.append(summarize(name, recs))
    md = "# Final evaluation\n\n" + md_table(rows)
    (results_dir() / "final_eval.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
