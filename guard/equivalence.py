from __future__ import annotations

from common.llm import LLM, json_from_text


SYSTEM = (
    "Compare two questions for semantic cache reuse. Answer only with JSON. "
    "Equivalent means they require the same answer, constraints, entities, values, and scope. "
    "If a changed condition could change the answer, return false."
)


class EquivalenceVerifier:
    """Fail-safe, document-independent equivalence check."""

    def __init__(self):
        self.llm = LLM("judge")

    def is_same(self, first: str, second: str) -> bool:
        for a, b in ((first, second), (second, first)):
            prompt = (
                "Question A:\n"
                f"{a}\n\n"
                "Question B:\n"
                f"{b}\n\n"
                'Return JSON: {"equivalent": true} or {"equivalent": false}'
            )
            try:
                result = self.llm.generate(prompt, system=SYSTEM)
            except (ConnectionError, TimeoutError):
                return False
            parsed = json_from_text(result.text)
            if not isinstance(parsed, dict) or parsed.get("equivalent") is not True:
                return False
        return True
