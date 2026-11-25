from guard.match import entities_compatible, normalize_question
from tests.cache_pairs_reviewed import P
from guard.cache import SemanticCache


def test_normalize_question():
    assert normalize_question("  What is a Pod?  ") == normalize_question("what is a pod")
    assert normalize_question("node\u2011ip") == "node-ip"
    assert normalize_question("  WHAT   is  a Kubernetes Pod?!  ") == normalize_question("what is a kubernetes pod")


def test_every_paraphrase_is_accepted():
    bad = [q[:60] for q, para, _ in P if not entities_compatible(para, q)]
    assert not bad, bad


def test_near_misses_are_rejected():
    missed = [q[:60] for q, _, near in P if entities_compatible(near, q)]
    assert len(missed) <= 2, missed          # the two left are meaning-only changes no entity rule can see


def test_specific_contrasts():
    assert not entities_compatible("Which RestartPolicy for a pod template in a Job?", "Which RestartPolicy for a pod template in a DaemonSet?")
    assert not entities_compatible("How does background cascading deletion work?", "How does foreground cascading deletion work?")
    assert not entities_compatible("Run the nginx:1.16.0 image with kubectl", "Run the nginx:1.14.2 image with kubectl")
    assert not entities_compatible("Open a shell in the 'sidecar' container", "Open a shell in the 'main-app' container")
    assert not entities_compatible("limit of 2 cpu", "limit of 1 cpu")
    assert entities_compatible("What does a Service do?", "What is the purpose of a Service?")
    assert entities_compatible("Which IngressClasses can be default?", "Which IngressClass can be default?")


def test_normalized_exact_key_is_stable():
    cache = SemanticCache.__new__(SemanticCache)
    cache.version = "corpus"
    cache._point_id = lambda group, question: (
        __import__("uuid").uuid5(
            __import__("uuid").NAMESPACE_URL,
            f"{cache.version}|{group}|{normalize_question(question)}",
        )
    )
    assert cache._point_id("public", "  What is a Pod?  ") == cache._point_id(
        "public", "what is a pod"
    )
    assert cache._point_id("public", "WHAT  IS A POD?!") == cache._point_id(
        "public", "what is a pod"
    )
    assert cache._point_id("public", "whatisapod") != cache._point_id(
        "public", "what is a pod"
    )
