"""Judge reliability: hand-label 30 answers WITHOUT seeing the judge's verdict, then report agreement.

  python -m eval.judge_agreement sample   # writes results/hand_label_sheet.csv (fill the my_label column with 1/0)
  python -m eval.judge_agreement score    # percent agreement + Cohen's kappa
"""
from __future__ import annotations

import csv
import json
import random
import sys

from common.config import results_dir
from common.io import read_jsonl
from eval.golden import load_golden
from eval.metrics import cohens_kappa

SRC = "final_full_router.jsonl"


def sample() -> None:
    gold = {q["id"]: q for q in load_golden()}
    recs = read_jsonl(results_dir() / SRC)
    random.seed(11)
    pick = random.sample(recs, 30)
    with open(results_dir() / "hand_label_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "question", "reference_answer", "answer", "my_label"])
        for r in pick:
            q = gold[r["id"]]
            w.writerow([r["id"], r["type"], q["question"], q["reference_answer"], r["clean_answer"], ""])
    print("Fill the my_label column (1 = correct, 0 = incorrect) without looking at the judge's verdicts.")


def score() -> None:
    verdict = {r["id"]: int(r["correct"]) for r in read_jsonl(results_dir() / SRC)}
    with open(results_dir() / "hand_label_sheet.csv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["my_label"].strip() in ("0", "1")]
    mine = [int(r["my_label"]) for r in rows]
    judge = [verdict[r["id"]] for r in rows]
    out = {"n": len(rows), "agreement": sum(a == b for a, b in zip(mine, judge)) / max(len(rows), 1),
           "cohens_kappa": cohens_kappa(mine, judge)}
    (results_dir() / "judge_agreement.json").write_text(json.dumps(out, indent=2))
    print(out)


if __name__ == "__main__":
    sample() if sys.argv[1:] == ["sample"] else score()
