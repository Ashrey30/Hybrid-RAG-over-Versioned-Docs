"""Citation check: strip and flag any cited chunk ID that is not in the retrieved set."""
from __future__ import annotations

import re

ID = r"[0-9a-f]{10}"
BRACKET = re.compile(rf"(\s*)\[({ID}(?:\s*[,;]\s*{ID})*)\]")


def check_citations(text: str, allowed_ids: set) -> tuple[str, list[str], list[str]]:
    """Returns (clean_text, valid_ids_in_order, stripped_ids)."""
    valid: list[str] = []
    stripped: list[str] = []

    def repl(m: re.Match) -> str:
        ids = re.split(r"\s*[,;]\s*", m.group(2))
        keep = [i for i in ids if i in allowed_ids]
        stripped.extend(i for i in ids if i not in allowed_ids)
        valid.extend(keep)
        return m.group(1) + "".join(f"[{i}]" for i in keep) if keep else ""

    clean = BRACKET.sub(repl, text)
    return clean, list(dict.fromkeys(valid)), list(dict.fromkeys(stripped))
