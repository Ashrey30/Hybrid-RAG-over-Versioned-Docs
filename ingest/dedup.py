"""Store identical chunks once, preserving document access and release metadata."""
from __future__ import annotations


def dedup_chunks(per_version: dict[str, list[dict]], order: list[str]):
    merged: dict[str, dict] = {}
    before: dict[str, int] = {}
    for v in order:
        chunks = per_version.get(v, [])
        before[v] = len(chunks)
        for c in chunks:
            access_group = c.get("access_group", "public")
            if access_group not in {"public", "restricted"}:
                raise ValueError(f"Unsupported document access group: {access_group!r}")
            h = c["content_hash"]
            if h in merged:
                if v not in merged[h]["versions"]:
                    merged[h]["versions"].append(v)
                merged[h]["access_group"] = access_group
            else:
                d = dict(c)
                d["versions"] = [v]
                d["access_group"] = access_group
                merged[h] = d
    latest = order[-1]
    out = []
    for h, d in merged.items():
        d["is_latest"] = latest in d["versions"]
        d["version"] = d["versions"][-1]
        d["chunk_id"] = h[:10]
        out.append(d)
    stats = {
        "chunks_before": before,
        "chunks_before_total": sum(before.values()),
        "chunks_after": len(out),
        "shared_across_releases": sum(1 for d in out if len(d["versions"]) > 1),
        "restricted": sum(1 for d in out if d["access_group"] == "restricted"),
        "latest_only_chunks": sum(1 for d in out if d["is_latest"]),
    }
    return out, stats
