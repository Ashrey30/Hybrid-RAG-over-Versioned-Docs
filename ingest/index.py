"""Fetch docs -> chunk -> dedup -> embed -> index into one Qdrant collection (dense + BM25).

Run:  python -m ingest.index
"""
from __future__ import annotations

import json
import hashlib
import uuid

from qdrant_client import QdrantClient, models
from tqdm import tqdm

from common.config import cfg, data_dir, qdrant_url, results_dir
from common.embed import embed_passages, sparse_passages
from common.cache_identity import runtime_fingerprint
from common.io import write_jsonl
from ingest.build_corpus import fetch_all_versions
from ingest.chunk import build_chunks
from ingest.dedup import dedup_chunks

DIM = 384


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def create_collection(client: QdrantClient, name: str) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config={"dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    client.create_payload_index(name, "is_latest", models.PayloadSchemaType.BOOL)
    client.create_payload_index(name, "access_group", models.PayloadSchemaType.KEYWORD)


def main() -> None:
    c = cfg()
    versions = c["corpus"].get("versions", [])
    order = [v["name"] for v in versions] if versions else ["unversioned"]
    docs = fetch_all_versions()
    ch = c["chunking"]
    per_version = {}
    for version in order:
        per_version[version] = []
        for doc in docs[version]:
            document_chunks = build_chunks(
                doc["doc_id"], doc["title"], doc["body"], ch["target_tokens"], ch["max_tokens"]
            )
            for chunk in document_chunks:
                chunk["access_group"] = doc.get("access_group", "public")
            per_version[version].extend(document_chunks)
    chunks, stats = dedup_chunks(per_version, order)
    print(json.dumps(stats, indent=2))
    (results_dir() / "ingest_stats.json").write_text(json.dumps(stats, indent=2))
    write_jsonl(data_dir() / "chunks.jsonl", chunks)
    chunk_hashes = sorted(
        (x["chunk_id"], x["doc_id"], x["title"], x["section_path"], x["content_hash"], x["access_group"])
        for x in chunks
    )
    fingerprint = hashlib.sha256(
        json.dumps(chunk_hashes, separators=(",", ":")).encode()
    ).hexdigest()
    (data_dir() / "corpus_manifest.json").write_text(
        json.dumps({
            "fingerprint": fingerprint,
            "runtime_fingerprint": runtime_fingerprint(),
            "chunk_count": len(chunks),
        }, indent=2),
        encoding="utf-8",
    )

    client = QdrantClient(url=qdrant_url(), timeout=120, check_compatibility=False)
    name = c["qdrant"]["collection"]
    create_collection(client, name)
    B = 64
    for i in tqdm(range(0, len(chunks), B), desc="indexing"):
        batch = chunks[i : i + B]
        texts = [x["text"] for x in batch]
        dense = embed_passages(texts)
        sparse = sparse_passages(texts)
        points = [
            models.PointStruct(
                id=point_id(x["chunk_id"]),
                vector={"dense": dense[j].tolist(), "bm25": models.SparseVector(indices=sparse[j][0], values=sparse[j][1])},
                payload={k: x[k] for k in ("chunk_id", "doc_id", "title", "section_path", "text", "content_hash",
                                           "version", "versions", "is_latest", "access_group")},
            )
            for j, x in enumerate(batch)
        ]
        client.upsert(name, points=points, wait=True)
    print(f"Indexed {len(chunks)} chunks into '{name}'.")


if __name__ == "__main__":
    main()
