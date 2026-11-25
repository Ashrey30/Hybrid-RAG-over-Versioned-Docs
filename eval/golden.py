from __future__ import annotations

from common.config import data_dir
from common.io import read_jsonl

NEEDS_RETRIEVAL = ("single", "multi", "version_trap")


def load_golden(path=None) -> list[dict]:
    rows = read_jsonl(path or data_dir() / "golden.jsonl")
    if not rows:
        raise SystemExit("data/golden.jsonl not found. Run `make golden-draft`, review by hand, save as data/golden.jsonl.")
    return rows
