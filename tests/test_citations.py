from generate.answer import is_abstention, strip_markdown_links
from generate.citations import check_citations

A, B = "a" * 10, "b" * 10


def test_invalid_ids_stripped_and_flagged():
    clean, valid, stripped = check_citations(f"x [{A}] y [{B}].", {A})
    assert clean == f"x [{A}] y."
    assert valid == [A] and stripped == [B]


def test_multi_id_bracket():
    clean, valid, stripped = check_citations(f"x [{A}, {B}].", {A})
    assert clean == f"x [{A}]." and stripped == [B]


def test_no_citations_untouched():
    assert check_citations("hello", set()) == ("hello", [], [])


def test_abstention_detection():
    assert is_abstention("I don't know.")
    assert not is_abstention("Use kubectl rollout undo.")


def test_markdown_links_are_returned_as_readable_text():
    assert strip_markdown_links("See the [troubleshooting guide](/docs/help). [a1b2c3d4e5]") == (
        "See the troubleshooting guide. [a1b2c3d4e5]"
    )
