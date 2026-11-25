"""Draft the 120-question golden set with an LLM (gold chunk IDs come for free).

Writes data/golden_draft.jsonl. REVIEW EVERY ROW BY HAND (delete ambiguous questions, fix weak
reference answers), then save the result as data/golden.jsonl.

Types: single 50, multi 20, unanswerable 15, version_trap 15, conversational 20.
Over-generates ~20% per type so you can drop weak ones during review.
"""
from __future__ import annotations

import random
from collections import defaultdict

from tqdm import tqdm

from common.config import data_dir
from common.io import read_jsonl, write_jsonl
from common.llm import LLM, QuotaExhausted, json_from_text

SYS = "You write evaluation questions for a documentation Q&A system. Reply with JSON only."
RULES = ('Reply as JSON: {"question": "...", "reference_answer": "..."}. The question must be self-contained '
         '(never say "the text", "the passage" or "the chunk"), specific, and phrased like a real user question.')

CONVERSATIONAL = [
    ("Hi there!", "A short friendly greeting."),
    ("Hello, can you help me with some questions?", "Yes, a short friendly offer to help."),
    ("Good morning", "A short friendly greeting."),
    ("Thanks, that was helpful.", "You're welcome, brief."),
    ("Thank you so much!", "You're welcome, brief."),
    ("Can you explain that in simpler words?", "Offers to simplify; may ask which part."),
    ("Could you repeat that more briefly?", "Offers to restate briefly; may ask which part."),
    ("What can you help me with?", "Says it answers questions about the Kubernetes documentation."),
    ("Who are you?", "An assistant that answers questions about the Kubernetes documentation."),
    ("What does the acronym API stand for?", "Application Programming Interface."),
    ("What does YAML stand for?", "YAML Ain't Markup Language (originally Yet Another Markup Language)."),
    ("What is a container, in general terms?", "A lightweight, isolated package of an application and its dependencies sharing the host OS kernel."),
    ("What is the difference between TCP and UDP?", "TCP is connection-oriented and reliable; UDP is connectionless and does not guarantee delivery."),
    ("What does DNS do?", "Translates domain names into IP addresses."),
    ("What does CPU stand for?", "Central Processing Unit."),
    ("What is JSON?", "A lightweight text format for structured data using key-value pairs and arrays."),
    ("Ok, got it.", "Brief acknowledgement."),
    ("Great, one more question coming.", "Brief acknowledgement, invites the question."),
    ("Bye!", "A short goodbye."),
    ("Can you say that again?", "Offers to repeat or asks what to repeat."),
]


def ask(llm: LLM, prompt: str):
    r = llm.generate(prompt, system=SYS)
    j = json_from_text(r.text)
    if j and j.get("question") and j.get("reference_answer"):
        return j["question"].strip(), j["reference_answer"].strip()
    return None


def main() -> None:
    random.seed(7)
    chunks = read_jsonl(data_dir() / "chunks.jsonl")
    llm = LLM("judge")  # use the judge model so the generator's daily quota is saved
    latest = [c for c in chunks if c["is_latest"] and c["tokens"] >= 80]
    by_doc = defaultdict(list)
    for c in latest:
        by_doc[c["doc_id"]].append(c)
    rows: list[dict] = []

    def add(qtype, q, ref, gold, preview):
        rows.append({"id": f"{qtype[:3]}-{len(rows):03d}", "question": q, "type": qtype, "reference_answer": ref,
                     "gold_chunk_ids": gold, "_preview": preview[:400]})

    try:
        for c in tqdm(random.sample(latest, 60), desc="single"):
            r = ask(llm, f"Passage:\n{c['text']}\n\nWrite one question that can be answered from this passage alone, and its reference answer. {RULES}")
            if r:
                add("single", *r, [c["chunk_id"]], c["text"])

        pairs = [(a, b) for cs in by_doc.values() for a, b in zip(cs, cs[1:]) if a["section_path"] != b["section_path"]]
        for a, b in tqdm(random.sample(pairs, min(26, len(pairs))), desc="multi"):
            r = ask(llm, f"Passage A:\n{a['text']}\n\nPassage B:\n{b['text']}\n\nWrite one question that needs BOTH passages to answer fully, and its reference answer. {RULES}")
            if r:
                add("multi", *r, [a["chunk_id"], b["chunk_id"]], a["text"] + "\n---\n" + b["text"])

        for c in tqdm(random.sample(latest, 20), desc="unanswerable"):
            r = ask(llm, f"Passage:\n{c['text']}\n\nWrite one plausible question on the same topic that this passage does NOT answer (a related detail it never mentions). Set reference_answer to \"I don't know.\" {RULES}")
            if r:
                add("unanswerable", r[0], "I don't know.", [], c["text"])

        old = {(c["doc_id"], c["section_path"]): c for c in chunks if not c["is_latest"]}
        traps = [(old[(c["doc_id"], c["section_path"])], c) for c in latest if (c["doc_id"], c["section_path"]) in old]
        for o, n in tqdm(random.sample(traps, min(22, len(traps))), desc="version_trap"):
            r = ask(llm, f"OLD release passage:\n{o['text']}\n\nNEW release passage:\n{n['text']}\n\nWrite one question whose correct answer comes only from the NEW passage and would be answered differently (or wrongly) by the OLD one. Do not mention releases or versions. {RULES}")
            if r:
                add("version_trap", *r, [n["chunk_id"]], n["text"])
    except QuotaExhausted as e:
        print("Quota hit, saving what exists:", str(e)[:120])

    for q, ref in CONVERSATIONAL:
        add("conversational", q, ref, [], "")
    write_jsonl(data_dir() / "golden_draft.jsonl", rows)
    counts = defaultdict(int)
    for r in rows:
        counts[r["type"]] += 1
    print(dict(counts), "-> data/golden_draft.jsonl. Review by hand, then save as data/golden.jsonl (drop the _preview field if you like).")


if __name__ == "__main__":
    main()
