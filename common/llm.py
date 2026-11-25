"""The one LLM wrapper everything calls.

SQLite cache keyed on model+prompt, retries on rate limits, request/token throttling,
and a log of tokens and latency. Raises QuotaExhausted when a *daily* cap is hit so long
runs (the k-sweep) can stop cleanly and resume the next day from the cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass

from common.config import ROOT, cfg


class QuotaExhausted(RuntimeError):
    pass


class PromptTooLarge(RuntimeError):
    """HTTP 413: the single request exceeds the model's per-request token limit."""


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cached: bool
    model: str

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_THINK = re.compile(r"<think>.*?</think>", re.S)
DB_PATH = ROOT / "data" / "llm_cache.sqlite"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, text TEXT, pt INT, ct INT, latency_ms REAL, model TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS calls(ts REAL, role TEXT, model TEXT, pt INT, ct INT, latency_ms REAL, cached INT)")
    return con


def json_from_text(text: str):
    """Pull the first JSON object out of a model reply, or None."""
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        return json.loads(text[a : b + 1])
    except json.JSONDecodeError:
        return None


class LLM:
    def __init__(self, role: str):
        spec = cfg()["llm"][role]
        prov = cfg()["providers"][spec["provider"]]
        self.role = role
        self.model = spec["model"]
        self.temperature = spec.get("temperature", 0)
        self.max_tokens = spec.get("max_tokens", 500)
        self.rpm = spec.get("rpm", 25)
        self.tpm = spec.get("tpm", 7000)
        self.extra = spec.get("extra") or {}
        self.base_url = prov["base_url"]
        self.key_env = prov["key_env"]
        self._client = None
        self._req: deque = deque()
        self._tok: deque = deque()
        self._lock = threading.Lock()
        self._con = _connect()

    # -- internals -----------------------------------------------------
    def _client_(self):
        if self._client is None:
            from openai import OpenAI

            key = os.getenv(self.key_env)
            if not key:
                raise RuntimeError(f"{self.key_env} is not set (see .env.example)")
            self._client = OpenAI(api_key=key, base_url=self.base_url, timeout=60, max_retries=0)
        return self._client

    def _throttle(self, est_tokens: int) -> None:
        while True:
            now = time.time()
            while self._req and now - self._req[0] > 60:
                self._req.popleft()
            while self._tok and now - self._tok[0][0] > 60:
                self._tok.popleft()
            used = sum(t for _, t in self._tok)
            if (len(self._req) < self.rpm and used + est_tokens <= self.tpm) or not self._req:
                return
            time.sleep(1.0)

    def _log(self, r: LLMResult) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO calls VALUES (?,?,?,?,?,?,?)",
                (time.time(), self.role, self.model, r.prompt_tokens, r.completion_tokens, r.latency_ms, int(r.cached)),
            )
            self._con.commit()

    # -- public --------------------------------------------------------
    def generate(self, prompt: str, system: str | None = None, use_cache: bool = True) -> LLMResult:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        key = hashlib.sha256(
            json.dumps([self.model, self.temperature, self.max_tokens, system, prompt]).encode()
        ).hexdigest()
        if use_cache:
            with self._lock:
                row = self._con.execute(
                    "SELECT text, pt, ct, latency_ms FROM cache WHERE key=?", (key,)
                ).fetchone()
            if row:
                res = LLMResult(row[0], row[1], row[2], row[3], True, self.model)
                self._log(res)
                return res

        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        est = int(len(prompt) / 3.5) + len(system or "") // 3 + self.max_tokens
        last_err: Exception | None = None
        for attempt in range(6):
            self._throttle(est)
            t0 = time.perf_counter()
            try:
                r = self._client_().chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    extra_body=self.extra or None,
                )
            except RateLimitError as e:
                msg = str(e).lower()
                if "per day" in msg or "tpd" in msg or "rpd" in msg:
                    raise QuotaExhausted(str(e)) from e
                last_err = e
                time.sleep(min(10 * (attempt + 1), 60))
                continue
            except (APIConnectionError, APITimeoutError) as e:
                last_err = e
                time.sleep(2 ** (attempt + 1))
                continue
            except APIStatusError as e:
                if e.status_code == 413:
                    raise PromptTooLarge(str(e)) from e
                if e.status_code >= 500:
                    last_err = e
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise
            latency = (time.perf_counter() - t0) * 1000
            text = _THINK.sub("", r.choices[0].message.content or "").strip()
            usage = r.usage
            pt, ct = (usage.prompt_tokens, usage.completion_tokens) if usage else (est, 0)
            now = time.time()
            self._req.append(now)
            self._tok.append((now, pt + ct))
            res = LLMResult(text, pt, ct, latency, False, self.model)
            with self._lock:
                self._con.execute(
                    "INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)", (key, text, pt, ct, latency, self.model)
                )
                self._con.commit()
            self._log(res)
            return res
        raise RuntimeError(f"LLM call failed after retries: {last_err}")
