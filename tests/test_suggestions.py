from types import SimpleNamespace

from api.pipeline import RagPipeline
from retrieve.search import Retriever


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.scroll_args = None

    def scroll(self, **kwargs):
        self.scroll_args = kwargs
        return [SimpleNamespace(payload=payload) for payload in self.payloads], None


def _pipeline(payloads):
    pipeline = RagPipeline.__new__(RagPipeline)
    client = FakeClient(payloads)
    pipeline.retriever = SimpleNamespace(
        client=client,
        collection="documents",
        make_filter=Retriever.make_filter,
    )
    return pipeline, client


def test_suggestions_use_current_accessible_document_sections_and_shuffle_without_repeats():
    payloads = [
        {"title": f"Guide {index}", "section_path": f"Guide {index} > Topic {index}"}
        for index in range(8)
    ]
    pipeline, client = _pipeline(payloads)

    first = pipeline.suggestions("public")
    second = pipeline.suggestions("public", exclude=[item["key"] for item in first])

    assert len(first) == len(second) == 4
    assert {item["key"] for item in first}.isdisjoint(item["key"] for item in second)
    assert all(item["question"].startswith('What can you tell me about "Topic ') for item in first + second)
    assert client.scroll_args["limit"] == 500
    assert client.scroll_args["with_payload"] == ["title", "section_path"]
    assert client.scroll_args["scroll_filter"].must[0].match.any == ["public"]
    assert client.scroll_args["scroll_filter"].must[1].key == "is_latest"


def test_suggestions_use_document_title_when_section_is_only_boilerplate():
    pipeline, _ = _pipeline([{"title": "Pod Overhead", "section_path": "Pod Overhead > Usage example"}])
    suggestions = pipeline.suggestions()

    assert suggestions == [
        {
            "key": suggestions[0]["key"],
            "question": 'What can you tell me about "Pod Overhead"?',
            "source": "Pod Overhead",
        }
    ]


def test_suggestions_fall_back_to_document_title_for_question_or_instruction_sections():
    pipeline, _ = _pipeline([
        {
            "title": "Pod Lifecycle",
            "section_path": "Pod Lifecycle > When should you use a readiness probe?",
        },
        {
            "title": "Security Context",
            "section_path": "Security Context > Set the security context for a Container",
        },
    ])

    suggestions = pipeline.suggestions(count=2)

    assert {item["question"] for item in suggestions} == {
        'What can you tell me about "Pod Lifecycle"?',
        'What can you tell me about "Set the security context for a Container"?',
    }


def test_suggestions_are_empty_when_no_accessible_documents_are_indexed():
    pipeline, _ = _pipeline([])

    assert pipeline.suggestions() == []
