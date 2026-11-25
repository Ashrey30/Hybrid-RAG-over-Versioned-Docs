"""Live semantic-cache smoke test over data/golden.jsonl."""
from __future__ import annotations

import argparse
import json
import os
import time

import requests

from common.io import read_jsonl
from common.llm import LLM, json_from_text
from eval.api_auth import authenticate_api


PARAPHRASE_SYSTEM = (
    "Rewrite the Kubernetes question as one paraphrase that asks exactly the same thing. "
    "Preserve every entity, resource name, version, value, and constraint. "
    "Return JSON only."
)


def api_json(method: str, url: str, body: dict | None = None, session: requests.Session | None = None):
    client = session or requests.Session()
    last_error = None
    for attempt in range(3):
        try:
            response = client.request(method, url, json=body, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"API request failed after 3 attempts: {url}") from last_error


def clear_cache(qdrant_url: str, collection: str) -> bool:
    try:
        response = requests.delete(
            f"{qdrant_url}/collections/{collection}", timeout=30
        )
        return response.status_code in (200, 404)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not clear {collection}: {exc}") from exc


def paraphrase(llm: LLM, question: str) -> str:
    prompt = (
        f"Original question:\n{question}\n\n"
        'Return JSON: {"paraphrase": "the rewritten question"}'
    )
    parsed = json_from_text(llm.generate(prompt, system=PARAPHRASE_SYSTEM).text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("paraphrase"), str):
        raise RuntimeError(f"Could not generate a valid paraphrase for: {question}")
    return parsed["paraphrase"].strip()


def citation_ids(response: dict) -> set[str]:
    return {
        c["title"] + "|" + c["section"]
        for c in response.get("citations", [])
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--api", default=os.getenv("RAG_API_URL", "http://localhost:8000"))
    parser.add_argument("--qdrant", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--collection", default="qa_cache")
    parser.add_argument("--output", default="results/live_cache_golden.jsonl")
    parser.add_argument("--ids", default="", help="Comma-separated golden IDs to run")
    args = parser.parse_args()

    rows = read_jsonl("data/golden.jsonl")
    rows = [
        row for row in rows
        if row.get("type") in {"single", "multi", "version_trap"}
    ][: args.limit]
    if args.ids:
        selected = {value.strip() for value in args.ids.split(",") if value.strip()}
        rows = [row for row in rows if row["id"] in selected]
    if not rows:
        raise SystemExit("No usable rows in data/golden.jsonl")

    session = requests.Session()
    user = authenticate_api(session, args.api, require_admin=True)
    clear_cache(args.qdrant, args.collection)
    judge = LLM("judge")
    records = []

    for index, row in enumerate(rows, start=1):
        question = row["question"]
        print(f"[{index}/{len(rows)}] {question}".encode("ascii", "backslashreplace").decode("ascii"))

        original = api_json("POST", f"{args.api}/ask", {"question": question}, session)
        repeated = api_json("POST", f"{args.api}/ask", {"question": question}, session)
        rewritten = paraphrase(judge, question)
        semantic = api_json("POST", f"{args.api}/ask", {"question": rewritten}, session)

        original_trace = original["trace"]
        repeated_trace = repeated["trace"]
        semantic_trace = semantic["trace"]
        records.append({
            "id": row["id"],
            "original": question,
            "paraphrase": rewritten,
            "reference_answer": row.get("reference_answer"),
            "original_status": (
                original_trace.get("cache_tier", "hit")
                if original_trace["cache_hit"] else "miss"
            ),
            "repeated_status": (
                repeated_trace.get("cache_tier", "hit")
                if repeated_trace["cache_hit"] else "miss"
            ),
            "paraphrase_status": (
                semantic_trace.get("cache_tier", "hit")
                if semantic_trace["cache_hit"] else "miss"
            ),
            "original_answer": original["answer"],
            "repeated_answer_matches_original": repeated["answer"] == original["answer"],
            "paraphrase_answer": semantic["answer"],
            "paraphrase_answer_matches_original": semantic["answer"] == original["answer"],
            "original_citations": sorted(citation_ids(original)),
            "repeated_citations_match_original": citation_ids(repeated) == citation_ids(original),
            "paraphrase_citations": sorted(citation_ids(semantic)),
            "paraphrase_citations_match_original": citation_ids(semantic) == citation_ids(original),
        })

    os.makedirs("results", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({
        "questions": len(records),
        "account_role": user["role"],
        "exact_hits": sum(r["repeated_status"] == "exact" for r in records),
        "semantic_hits": sum(r["paraphrase_status"] == "semantic" for r in records),
        "repeated_answer_matches": sum(r["repeated_answer_matches_original"] for r in records),
        "repeated_citation_matches": sum(r["repeated_citations_match_original"] for r in records),
        "semantic_answer_matches": sum(r["paraphrase_answer_matches_original"] for r in records),
        "semantic_citation_matches": sum(r["paraphrase_citations_match_original"] for r in records),
        "output": args.output,
    }, indent=2))


if __name__ == "__main__":
    main()
