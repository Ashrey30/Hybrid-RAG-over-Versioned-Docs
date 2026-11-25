"""The full request pipeline: guard -> embed -> cache -> router -> retrieve(+rerank) -> generate -> citation check.

Three early exits: a flagged prompt, a cache hit, or a router choice of k=0.
"""
from __future__ import annotations

import hashlib
import random
import re
import time

from common.config import ROOT, cfg
from common.embed import embed_query
from common.llm import LLM
from generate.answer import generate_answer, strip_markdown_links
from generate.citations import check_citations
from generate.prompt import capability_answer
from guard.match import entities_compatible
from retrieve.search import Retriever

BRACKET_ID = re.compile(r"\[([0-9a-f]{10})\]")
_GENERIC_SECTIONS = {
    "example",
    "examples",
    "options",
    "options inherited from parent commands",
    "overview",
    "synopsis",
    "usage",
    "usage example",
    "notes",
    "ownership",
}
_QUESTION_SECTION_START = re.compile(
    r"^(?:how|what|when|where|why|who|which|can|could|does|do|is|should)\b",
    re.IGNORECASE,
)


def _suggestion_label(value: str) -> str:
    value = re.sub(r"\s*\{#[^}]+\}", "", value)
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip(" .:-")


def retrieval_k_for_question(question: str, predicted_k: int) -> int:
    """Keep multi-part questions broad enough to retrieve each evidence part."""
    complexity_markers = (
        question.count("?") > 1,
        len(question) >= 180,
        ", and " in question.lower(),
        " and what " in question.lower(),
        " and how " in question.lower(),
        " and which " in question.lower(),
        " and once " in question.lower(),
    )
    if predicted_k > 0 and any(complexity_markers):
        return max(predicted_k, 10)
    return predicted_k


class RagPipeline:
    def __init__(self, use_guard: bool = True, use_cache: bool | None = None, use_router: bool = True,
                 fixed_k: int = 5, cache_version: str | None = None):
        if use_cache is None:   # default comes from config.yaml (cache.enabled)
            use_cache = bool(cfg()["cache"].get("enabled", True))
        self.retriever = Retriever()
        self.llm = LLM("generator")
        self.fixed_k = fixed_k
        self.guard = None
        if use_guard:
            from guard.injection import InjectionGuard

            self.guard = InjectionGuard()
        self.cache = None
        self.verifier = None
        if use_cache:
            from guard.cache import SemanticCache

            self.cache = SemanticCache(self.retriever.client, version=cache_version)
            self.cache.ensure()
            if cfg()["cache"].get("use_verifier", True) or cfg()["cache"].get("semantic_enabled", False):
                from guard.equivalence import EquivalenceVerifier

                self.verifier = EquivalenceVerifier()
        self.router = None
        if use_router and (ROOT / cfg()["router"]["path"]).exists():
            from retrieve.router import Router

            self.router = Router.load()

    def suggestions(self, group: str = "public", exclude: list[str] | None = None, count: int = 4) -> list[dict]:
        if count <= 0:
            return []
        points, _ = self.retriever.client.scroll(
            collection_name=self.retriever.collection,
            scroll_filter=self.retriever.make_filter(group, latest_only=True),
            limit=500,
            with_payload=["title", "section_path"],
            with_vectors=False,
        )
        candidates: dict[str, dict] = {}
        seen_questions: set[str] = set()
        for point in points:
            payload = point.payload or {}
            title = _suggestion_label(str(payload.get("title", "")))
            sections = [_suggestion_label(part) for part in str(payload.get("section_path", "")).split(" > ")]
            sections = [part for part in sections if part and part.casefold() != title.casefold()]
            topic = next(
                (
                    part for part in reversed(sections)
                    if part.casefold() not in _GENERIC_SECTIONS
                    and not _QUESTION_SECTION_START.match(part)
                    and "?" not in part
                ),
                title,
            )
            if not topic:
                continue
            question = f'What can you tell me about "{topic}"?'
            normalized_question = question.casefold()
            if normalized_question in seen_questions:
                continue
            seen_questions.add(normalized_question)
            key = hashlib.sha256(f"{title}\0{topic}".casefold().encode("utf-8")).hexdigest()[:16]
            candidates.setdefault(key, {
                "key": key,
                "question": question,
                "source": title,
            })

        excluded = set(exclude or [])
        available = [item for key, item in candidates.items() if key not in excluded]
        if len(available) < count:
            available.extend(item for key, item in candidates.items() if key in excluded)
        return random.sample(available, min(count, len(available)))

    def ask(self, question: str, group: str = "public") -> dict:
        timings: dict = {}
        t_all = time.perf_counter()
        trace = {"guard": "skipped", "cache_hit": False, "k": 0, "tokens": 0, "timings_ms": timings}

        def lap(name: str, t0: float) -> None:
            timings[name] = round((time.perf_counter() - t0) * 1000, 1)

        def finish(resp: dict) -> dict:
            timings["total"] = round((time.perf_counter() - t_all) * 1000, 1)
            resp["trace"] = trace
            return resp

        if self.guard:
            s = time.perf_counter()
            blocked, score = self.guard.check(question)
            lap("guard", s)
            trace["guard"] = "blocked" if blocked else "pass"
            if blocked:
                return finish({"answer": "This request was blocked by the prompt-injection guard.", "status": "blocked",
                               "citations": [], "_debug": {"retrieved_groups": [], "cited_chunk_ids": [], "guard_score": score}})

        answer = capability_answer(question)
        if answer is not None:
            return finish({"answer": answer, "status": "answered", "citations": [],
                           "_debug": {"retrieved_groups": [], "cited_chunk_ids": []}})

        s = time.perf_counter()
        qvec = embed_query(question)
        lap("embed", s)

        pre = None   # retrieval done while verifying a cache candidate; reused below if the candidate is rejected
        if self.cache:
            s = time.perf_counter()
            mode = cfg()["retrieval"]["mode"]
            hit, tier = None, ""
            cache_cfg = cfg()["cache"]
            if cache_cfg.get("exact_enabled", True):
                hit = self.cache.lookup_exact(question, group)
                tier = "exact" if hit else ""
            if not hit and cache_cfg.get("semantic_enabled", False):
                if self.verifier is None:
                    hit = None
                else:
                    candidates = self.cache.lookup(qvec, group, limit=5)   # 2. similarity finds candidates
                    for cand in candidates:
                        if not entities_compatible(question, cand["question"]):  # 3. entity guard
                            continue
                        cited = cand["debug"].get("cited_chunk_ids", [])
                        ok = True
                        if cited:                                           # 4. retrieval consistency
                            pre = self.retriever.retrieve(question, mode, 5, group, True, qvec=qvec)
                            overlap = len({h.chunk_id for h in pre.hits} & set(cited)) / len(cited)
                            ok = overlap >= cfg()["cache"].get("min_cited_overlap", 1.0)
                        else:
                            ok = False
                        if ok and self.verifier is not None:                # 5. semantic equivalence check
                            ok = self.verifier.is_same(question, cand["question"])
                        if ok:
                            hit, tier = cand, "semantic"
                            break
            lap("cache", s)
            if hit:
                trace.update(cache_hit=True, cache_tier=tier, k=hit["k"])
                cached_response = {**hit["response"]}
                if isinstance(cached_response.get("answer"), str):
                    cached_response["answer"] = strip_markdown_links(cached_response["answer"])
                return finish({**cached_response, "_debug": {**hit["debug"], "cache_group": hit["access_group"]}})

        s = time.perf_counter()
        predicted_k = self.router.predict_k(qvec) if self.router else self.fixed_k
        k = retrieval_k_for_question(question, predicted_k)
        lap("router", s)
        trace["k"] = k

        hits = []
        if k > 0:
            if pre is not None and k <= 5:       # top-k is a prefix of the top-5 already retrieved
                hits = pre.hits[:k]
            else:
                res = self.retriever.retrieve(question, cfg()["retrieval"]["mode"], k, group, True, qvec=qvec)
                hits = res.hits
                timings.update({n: v for n, v in res.timings_ms.items() if n != "embed"})

        s = time.perf_counter()
        gen = generate_answer(self.llm, question, hits)
        lap("generate", s)
        trace["tokens"] = gen.tokens

        by_id = {h.chunk_id: h.payload for h in hits}
        clean, valid, stripped = check_citations(strip_markdown_links(gen.text), set(by_id))
        order = list(dict.fromkeys(BRACKET_ID.findall(clean)))
        num = {cid: i + 1 for i, cid in enumerate(order)}
        answer = BRACKET_ID.sub(lambda m: f"[{num[m.group(1)]}]", clean)
        citations = [{"n": num[c], "title": by_id[c]["title"], "section": by_id[c]["section_path"],
                      "version": by_id[c]["version"], "is_latest": by_id[c]["is_latest"], "text": by_id[c]["text"]}
                     for c in order]
        if stripped:
            trace["stripped_citations"] = len(stripped)
        resp = {"answer": answer, "status": gen.status, "citations": citations}
        debug = {"retrieved_groups": sorted({h.payload["access_group"] for h in hits}), "cited_chunk_ids": order}

        if self.cache and gen.status == "answered":
            self.cache.store(qvec, group, question, {"response": resp, "k": k, "debug": debug})
        return finish({**resp, "_debug": debug})
