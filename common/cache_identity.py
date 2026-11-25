from __future__ import annotations

import hashlib
import json

from common.config import cfg, data_dir, ROOT


def _stable(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def corpus_fingerprint() -> str:
    manifest = data_dir() / "corpus_manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))["fingerprint"]

    chunks = data_dir() / "chunks.jsonl"
    if chunks.exists():
        return hashlib.sha256(chunks.read_bytes()).hexdigest()
    return hashlib.sha256(_stable(cfg()["corpus"]).encode()).hexdigest()


def runtime_fingerprint() -> str:
    c = cfg()
    relevant = {
        "models": c["models"],
        "retrieval": c["retrieval"],
        "router": c["router"],
        "llm": c["llm"],
        "chunking": c["chunking"],
    }
    code_paths = (
        ROOT / "generate" / "prompt.py",
        ROOT / "generate" / "answer.py",
        ROOT / "generate" / "citations.py",
    )
    code_hashes = [
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in code_paths
        if p.exists()
    ]
    relevant["code"] = code_hashes
    return hashlib.sha256(_stable(relevant).encode()).hexdigest()
