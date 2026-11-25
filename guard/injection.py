"""Prompt-injection check with Llama Prompt Guard 2 (gated model: accept the licence, run `hf auth login`)."""
from __future__ import annotations

from common.config import cfg

MALICIOUS = {"LABEL_1", "MALICIOUS", "INJECTION", "JAILBREAK"}


class InjectionGuard:
    def __init__(self, threshold: float | None = None):
        from transformers import pipeline

        self.threshold = threshold if threshold is not None else cfg()["guard"]["injection_threshold"]
        self.clf = pipeline("text-classification", model=cfg()["models"]["guard"], device=-1, top_k=None)

    def score(self, text: str) -> float:
        out = self.clf(text, truncation=True, max_length=512)
        items = out[0] if out and isinstance(out[0], list) else out
        return max((i["score"] for i in items if str(i["label"]).upper() in MALICIOUS), default=0.0)

    def check(self, text: str) -> tuple[bool, float]:
        s = self.score(text)
        return s >= self.threshold, s
