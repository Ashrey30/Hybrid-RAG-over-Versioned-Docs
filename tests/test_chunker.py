from ingest.chunk import approx_tokens, build_chunks, chunk_markdown

DOC = """Intro paragraph about pods.

## Rolling back

Use the rollout command to undo.

```bash
kubectl rollout undo deployment/app

# comment with a blank line above
kubectl rollout status deployment/app
```

## Scaling

Scale with replicas.
"""


def test_code_block_kept_whole():
    chunks = chunk_markdown("Deployments", DOC, 200, 300)
    code = [c for c in chunks if "rollout undo" in c["text"]]
    assert len(code) == 1
    assert "rollout status" in code[0]["text"]


def test_heading_inside_fence_not_split():
    body = "## A\n\n```\n# not a heading\nx\n```\n"
    chunks = chunk_markdown("T", body)
    assert all(c["section_path"] == "A" for c in chunks)


def test_cap_respected_for_prose():
    body = "## Big\n\n" + " ".join(f"Sentence number {i} is here." for i in range(300))
    for c in chunk_markdown("T", body, 200, 300):
        assert c["tokens"] <= 300


def test_prefix_and_hash():
    a = build_chunks("d.md", "Deployments", DOC)
    b = build_chunks("d.md", "Deployments", DOC)
    assert a[0]["text"].startswith("Deployments")
    assert [x["content_hash"] for x in a] == [x["content_hash"] for x in b]
    assert approx_tokens("a b c") > 3
