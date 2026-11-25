"""Push the golden set (dataset) and the router (model), each with a card.   Needs HF_TOKEN with write access.
Usage: python scripts/publish_hf.py <hf-username>
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent

DATASET_CARD = """---
license: cc-by-4.0
task_categories: [question-answering]
language: [en]
---
# Hybrid RAG golden set

120 hand-reviewed questions over the Kubernetes documentation at two releases.
Types: single-chunk (50), two-chunk (20), unanswerable (15), version trap (15), conversational (20).
Fields: id, question, type, reference_answer, gold_chunk_ids. Gold chunk IDs are the first 10 hex chars of the
chunk's content hash (see the code repo for the chunker). Questions were drafted with an LLM and reviewed by hand.
"""

MODEL_CARD = """---
license: mit
library_name: scikit-learn
---
# Adaptive retrieval router

Logistic regression on bge-small-en-v1.5 query embeddings (384-d). Predicts how many chunks to retrieve: k in {0, 2, 5, 10}.
Labels: the smallest k that produced a correct answer on the golden set (5 if none did). Trained on ~120 examples;
treat results as indicative (see 5-fold CV and bootstrap intervals in the code repo).
Load: `joblib.load("router.joblib").predict_proba(embedding.reshape(1, -1))`.
"""


def main(user: str) -> None:
    api = HfApi()
    ds, md = f"{user}/hybrid-rag-golden-set", f"{user}/hybrid-rag-router"
    api.create_repo(ds, repo_type="dataset", exist_ok=True)
    api.create_repo(md, repo_type="model", exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "README.md").write_text(DATASET_CARD)
        api.upload_folder(folder_path=t, repo_id=ds, repo_type="dataset")
    api.upload_file(path_or_fileobj=str(ROOT / "data" / "golden.jsonl"), path_in_repo="golden.jsonl", repo_id=ds, repo_type="dataset")
    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "README.md").write_text(MODEL_CARD)
        api.upload_folder(folder_path=t, repo_id=md, repo_type="model")
    api.upload_file(path_or_fileobj=str(ROOT / "models" / "router.joblib"), path_in_repo="router.joblib", repo_id=md, repo_type="model")
    print("published", ds, md)


if __name__ == "__main__":
    main(sys.argv[1])
