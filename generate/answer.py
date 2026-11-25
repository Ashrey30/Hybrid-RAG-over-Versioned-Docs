from __future__ import annotations

import re
from dataclasses import dataclass

from common.llm import LLM, PromptTooLarge
from generate.prompt import MAX_CONTEXT_CHARS, build_prompt

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def is_abstention(text: str) -> bool:
    t = text.lower().replace("’", "'").strip()
    return t.startswith("i don't know") or ("i don't know" in t and len(t) < 120)


def strip_markdown_links(text: str) -> str:
    return _MARKDOWN_LINK.sub(r"\1", text)


@dataclass
class GenResult:
    text: str
    status: str          # "answered" | "abstained"
    tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


def generate_answer(llm: LLM, question: str, hits) -> GenResult:
    budget = MAX_CONTEXT_CHARS
    for attempt in range(3):          # on a 413, halve the context budget and retry
        system, user = build_prompt(question, hits, budget)
        try:
            r = llm.generate(user, system=system)
            break
        except PromptTooLarge:
            if attempt == 2:
                raise
            budget //= 2
    return GenResult(r.text, "abstained" if is_abstention(r.text) else "answered",
                     r.tokens, r.prompt_tokens, r.completion_tokens, r.latency_ms)
