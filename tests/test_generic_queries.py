from types import SimpleNamespace

import api.pipeline as pipeline_module
from api.pipeline import RagPipeline
from generate.prompt import SYSTEM_NO_CONTEXT, SYSTEM_RAG, build_prompt, capability_answer


def test_capability_questions_get_a_citation_free_answer_without_pipeline_services():
    pipeline = RagPipeline.__new__(RagPipeline)
    pipeline.guard = None

    response = pipeline.ask("What can you help me with?")

    assert response["status"] == "answered"
    assert "documents indexed in this app" in response["answer"]
    assert response["citations"] == []
    assert response["_debug"]["retrieved_groups"] == []
    assert response["trace"]["k"] == 0


def test_capability_match_does_not_capture_document_questions():
    assert capability_answer("Who are you?") is not None
    assert capability_answer("How do I configure a Kubernetes service?") is None


def test_rag_prompt_separates_general_questions_from_document_questions():
    hit = SimpleNamespace(chunk_id="0123456789", payload={"text": "An unrelated Kubernetes passage."})

    system, _ = build_prompt("What is the difference between TCP and UDP?", [hit])

    assert "simple general-knowledge questions" in system
    assert "ignore unrelated retrieved context" in system
    assert "use ONLY relevant context" in system
    assert "clear, polished prose" in system
    assert "output Markdown links" in system
    assert "[0123456789]" in build_prompt("How do I configure this?", [hit])[1]
    assert "simple general-knowledge" in SYSTEM_NO_CONTEXT
    assert "cite every factual" in SYSTEM_RAG


def test_cached_answers_do_not_expose_raw_markdown_links(monkeypatch):
    class FakeCache:
        def lookup_exact(self, question, group):
            return {
                "response": {
                    "answer": "See the [troubleshooting guide](/docs/help). [a1b2c3d4e5]",
                    "status": "answered",
                    "citations": [],
                },
                "debug": {},
                "access_group": group,
                "k": 5,
            }

    monkeypatch.setattr(pipeline_module, "embed_query", lambda question: [])
    pipeline = RagPipeline.__new__(RagPipeline)
    pipeline.guard = None
    pipeline.cache = FakeCache()

    response = pipeline.ask("Where can I find help?", "public")

    assert response["answer"] == "See the troubleshooting guide. [a1b2c3d4e5]"
