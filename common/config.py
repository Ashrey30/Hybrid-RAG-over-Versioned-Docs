from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def cfg() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def qdrant_url() -> str:
    return os.getenv("QDRANT_URL", cfg()["qdrant"]["url"])


def results_dir() -> Path:
    p = ROOT / "results"
    p.mkdir(exist_ok=True)
    return p


def data_dir() -> Path:
    p = ROOT / "data"
    p.mkdir(exist_ok=True)
    return p
