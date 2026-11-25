import pytest

from ingest.build_corpus import parse_markdown
from ingest.dedup import dedup_chunks


def mk(h, doc="a.md"):
    return {"doc_id": doc, "content_hash": h * 8, "text": h}


def test_identical_chunks_stored_once_and_flagged():
    per = {"v1": [mk("a"), mk("b")], "v2": [mk("a"), mk("c")]}
    out, stats = dedup_chunks(per, ["v1", "v2"])
    assert stats["chunks_before_total"] == 4 and stats["chunks_after"] == 3
    by = {c["text"]: c for c in out}
    assert by["a"]["versions"] == ["v1", "v2"] and by["a"]["is_latest"]
    assert not by["b"]["is_latest"]  # only in the old release
    assert by["c"]["is_latest"]
    assert stats["shared_across_releases"] == 1
    assert all(chunk["access_group"] == "public" for chunk in out)


def test_document_front_matter_defaults_to_public_and_supports_explicit_restriction():
    assert parse_markdown("---\ntitle: Public guide\n---\nBody", "fallback") == (
        "Public guide",
        "Body",
        "public",
    )
    assert parse_markdown("---\ntitle: Private guide\naccess_group: restricted\n---\nBody", "fallback") == (
        "Private guide",
        "Body",
        "restricted",
    )


def test_document_front_matter_rejects_unknown_access_group():
    with pytest.raises(ValueError, match="access_group"):
        parse_markdown("---\naccess_group: internal\n---\nBody", "fallback")


def test_deduplicated_chunks_keep_latest_version_access_group():
    per = {
        "v1": [{**mk("a"), "access_group": "restricted"}],
        "v2": [{**mk("a"), "access_group": "public"}],
    }

    chunks, _ = dedup_chunks(per, ["v1", "v2"])

    assert chunks[0]["access_group"] == "public"


def test_deduplication_rejects_unknown_access_group():
    with pytest.raises(ValueError, match="Unsupported document access group"):
        dedup_chunks({"v1": [{**mk("a"), "access_group": "internal"}]}, ["v1"])
