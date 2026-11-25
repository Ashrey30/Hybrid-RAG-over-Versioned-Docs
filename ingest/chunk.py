"""Heading-based chunker: ~200 tokens, hard cap ~300, code blocks kept whole,
title + section path prepended. Token counts are a cheap word-based estimate."""
from __future__ import annotations

import hashlib
import re

HEADING = re.compile(r"^(#{1,4})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3) + 1


def split_sections(body: str) -> list[tuple[str, list[str]]]:
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = []
    cur_path, cur = "", []
    in_code = False
    for ln in body.splitlines():
        if FENCE.match(ln):
            in_code = not in_code
        m = None if in_code else HEADING.match(ln)
        if m:
            sections.append((cur_path, cur))
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
            cur_path = " > ".join(t for _, t in stack)
            cur = []
        else:
            cur.append(ln)
    sections.append((cur_path, cur))
    return [(p, ls) for p, ls in sections if any(x.strip() for x in ls)]


def _blocks(lines: list[str]) -> list[tuple[str, bool]]:
    """Paragraph / code blocks. Returns (text, is_code)."""
    blocks: list[tuple[str, bool]] = []
    cur: list[str] = []
    in_code = False

    def flush(code: bool):
        nonlocal cur
        if cur and any(x.strip() for x in cur):
            blocks.append(("\n".join(cur), code))
        cur = []

    for ln in lines:
        if FENCE.match(ln):
            if not in_code:
                flush(False)
                cur, in_code = [ln], True
            else:
                cur.append(ln)
                flush(True)
                in_code = False
        elif in_code:
            cur.append(ln)
        elif not ln.strip():
            flush(False)
        else:
            cur.append(ln)
    flush(in_code)
    return blocks


def _split_long(text: str, target: int) -> list[str]:
    parts, cur, cur_t = [], [], 0
    for s in re.split(r"(?<=[.!?])\s+", text):
        st = approx_tokens(s)
        if cur and cur_t + st > target:
            parts.append(" ".join(cur))
            cur, cur_t = [], 0
        cur.append(s)
        cur_t += st
    if cur:
        parts.append(" ".join(cur))
    return parts


def chunk_markdown(title: str, body: str, target: int = 200, cap: int = 300, min_tokens: int = 40) -> list[dict]:
    raw: list[dict] = []
    for path, lines in split_sections(body):
        items: list[tuple[str, bool]] = []
        for text, is_code in _blocks(lines):
            if not is_code and approx_tokens(text) > cap:
                items += [(p, False) for p in _split_long(text, target)]
            else:
                items.append((text, is_code))
        cur: list[str] = []
        cur_t = 0

        def flush():
            nonlocal cur, cur_t
            if cur:
                raw.append({"section_path": path, "text": "\n\n".join(cur), "tokens": cur_t})
            cur, cur_t = [], 0

        for text, _ in items:
            t = approx_tokens(text)
            if cur and cur_t + t > cap:
                flush()
            cur.append(text)
            cur_t += t
            if cur_t >= target:
                flush()
        flush()

    # merge tiny chunks into the previous one when it fits under the cap
    merged: list[dict] = []
    for c in raw:
        if merged and c["tokens"] < min_tokens and merged[-1]["tokens"] + c["tokens"] <= cap:
            merged[-1]["text"] += "\n\n" + c["text"]
            merged[-1]["tokens"] += c["tokens"]
        else:
            merged.append(dict(c))
    return merged


def build_chunks(doc_id: str, title: str, body: str, target: int = 200, cap: int = 300) -> list[dict]:
    out = []
    for i, c in enumerate(chunk_markdown(title, body, target, cap)):
        head = f"{title} > {c['section_path']}" if c["section_path"] else title
        text = f"{head}\n\n{c['text']}"
        norm = " ".join(text.split())
        out.append(
            {
                "doc_id": doc_id,
                "title": title,
                "section_path": c["section_path"] or title,
                "idx": i,
                "text": text,
                "tokens": c["tokens"],
                "content_hash": hashlib.sha256(norm.encode()).hexdigest(),
            }
        )
    return out
