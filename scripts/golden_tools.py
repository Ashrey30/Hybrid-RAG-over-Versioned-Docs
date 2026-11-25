"""Helpers for reviewing the golden set against the FULL indexed chunks (data/chunks.jsonl).

  python scripts/golden_tools.py review  data/golden.jsonl
      -> data/golden_review_full.md: full gold passages; for version traps the OLD release passage next to the NEW one
  python scripts/golden_tools.py orphans data/golden.jsonl [path-substring ...]
      -> lists questions whose gold chunk is missing from the index, or whose source doc path contains a substring
         (use after excluding a folder: e.g. reference/kubectl/generated)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rj(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    cmd, gpath, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
    qs = rj(gpath)
    chunks = rj(ROOT / "data" / "chunks.jsonl")
    by_id = {c["chunk_id"]: c for c in chunks}
    old = {}
    for c in chunks:
        if not c["is_latest"]:
            old.setdefault((c["doc_id"], c["section_path"]), []).append(c)

    if cmd == "orphans":
        bad = 0
        for q in qs:
            for g in q.get("gold_chunk_ids", []):
                c = by_id.get(g)
                why = "missing from index" if c is None else next((s for s in extra if s in c["doc_id"]), None)
                if why:
                    bad += 1
                    print(f"{q['id']:10} {q['type']:14} {why}: {c['doc_id'] if c else g}")
        print(f"\n{bad} questions affected out of {len(qs)}")
        return

    out = ROOT / "data" / "golden_review_full.md"
    with open(out, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(f"## {q['id']} ({q['type']})\n**Q:** {q['question']}\n\n**Ref:** {q['reference_answer']}\n\n")
            for g in q.get("gold_chunk_ids", []):
                c = by_id.get(g)
                if not c:
                    f.write(f"_gold chunk {g} not in index_\n\n")
                    continue
                f.write(f"**NEW** `{c['doc_id']}` ({', '.join(c['versions'])})\n\n```\n{c['text']}\n```\n\n")
                if q["type"] == "version_trap":
                    for o in old.get((c["doc_id"], c["section_path"]), []):
                        f.write(f"**OLD** ({', '.join(o['versions'])}) - does the answer differ from NEW?\n\n```\n{o['text']}\n```\n\n")
            f.write("---\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
