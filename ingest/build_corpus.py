"""Clone the docs at two releases (sparse checkout) and yield cleaned markdown documents."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from common.config import ROOT, cfg

FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
GLOSSARY = re.compile(r"\{\{<\s*glossary_tooltip[^>]*?text=\"([^\"]+)\"[^>]*>\}\}")
FEATURE = re.compile(r"\{\{<\s*feature-state[^>]*?for_k8s_version=\"([^\"]+)\"[^>]*?state=\"([^\"]+)\"[^>]*>\}\}")
SHORTCODE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.S)


def clone(repo: str, branch: str, dest: Path, subdir: str) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", "--branch", branch, "--filter=blob:none", "--sparse", repo, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", subdir], check=True)


def parse_markdown(raw: str, fallback_title: str) -> tuple[str, str, str]:
    title = fallback_title
    access_group = "public"
    m = FRONT.match(raw)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            raise ValueError("Invalid YAML front matter.") from exc
        if not isinstance(meta, dict):
            raise ValueError("Document front matter must be a mapping.")
        title = str(meta.get("title") or title)
        access_group = meta.get("access_group", "public")
        if not isinstance(access_group, str) or access_group not in {"public", "restricted"}:
            raise ValueError("Document access_group must be 'public' or 'restricted'.")
        raw = raw[m.end():]
    raw = GLOSSARY.sub(r"\1", raw)
    raw = FEATURE.sub(r"Feature state: \2 since \1.", raw)
    raw = SHORTCODE.sub("", raw)
    return title, raw.strip(), access_group


def load_docs(root: Path, subdir: str, exclude: list[str], max_docs: int = 0):
    base = root / subdir
    n = 0
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base).as_posix()
        if any(x in rel for x in exclude):
            continue
        title, body, access_group = parse_markdown(
            p.read_text(encoding="utf-8", errors="ignore"), p.stem.replace("-", " ").title()
        )
        if len(body) < 80:
            continue
        yield {"doc_id": rel, "title": title, "body": body, "access_group": access_group}
        n += 1
        if max_docs and n >= max_docs:
            return


def fetch_all_versions() -> dict[str, list[dict]]:
    c = cfg()["corpus"]
    out: dict[str, list[dict]] = {}
    if not c.get("versions"):
        source = ROOT / c.get("source", "data/documents")
        out["unversioned"] = list(load_docs(source, ".", c.get("exclude", []), c.get("max_docs", 0)))
        return out
    for v in c["versions"]:
        dest = ROOT / "data" / "raw" / v["name"]
        clone(c["repo"], v["branch"], dest, c["subdir"])
        out[v["name"]] = list(load_docs(dest, c["subdir"], c.get("exclude", []), c.get("max_docs", 0)))
    return out
