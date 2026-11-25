"""Map authenticated account roles to document groups used by retrieval."""
from __future__ import annotations


def allowed_groups(user_group: str) -> list[str]:
    return ["public", "restricted"] if user_group == "restricted" else ["public"]
