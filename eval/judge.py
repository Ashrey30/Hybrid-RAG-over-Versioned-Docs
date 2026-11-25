from __future__ import annotations

from common.llm import LLM, json_from_text
from generate.answer import is_abstention

SYSTEM = "You are a strict grader. Reply with JSON only."
TEMPLATE = """Question: {q}

Reference answer: {ref}

Candidate answer: {ans}

Is the candidate answer correct, i.e. consistent with the reference answer and not contradicting it? Ignore citation markers like [a1b2c3d4e5] and wording differences. Reply as JSON: {{"correct": true or false, "reason": "<one sentence>"}}"""


def judge_correct(llm: LLM, question: str, reference: str, answer: str, qtype: str) -> bool:
    if qtype == "unanswerable":      # correct means abstaining
        return is_abstention(answer)
    r = llm.generate(TEMPLATE.format(q=question, ref=reference, ans=answer), system=SYSTEM)
    j = json_from_text(r.text)
    return bool(j and j.get("correct") is True)
