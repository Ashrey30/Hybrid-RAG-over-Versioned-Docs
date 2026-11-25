"""Pure-Python checks that decide whether a cached question really is the *same* question as a new one.
Embedding similarity measures topic and barely notices a changed entity, so a candidate must also pass these rules.

Rules (a candidate is rejected if any fires):
  * version / number tokens differ ("nginx:1.14.2" vs "nginx:1.16.0", "limit of 1 cpu" vs "2 cpu");
  * Kubernetes kinds or tool names differ (DaemonSet vs Job, kubectl vs helm);
  * a contrast pair differs (foreground vs background, Linux vs Windows, hard vs soft ...);
  * a CamelCase / capitalised name in one question is missing from the other (DiskPressure vs MemoryPressure).
Except for version numbers, a rule only fires when each question has something the other lacks, so a paraphrase
that merely drops a word is not rejected for it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TRANS = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
                        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/\-]*")
QUOTED = [re.compile(p) for p in (r"`([^`]+)`", r'"([^"]+)"', r"(?<![A-Za-z0-9])'([^'\n]{1,40}?)'(?![A-Za-z0-9])")]

KINDS = {"deployment", "daemonset", "statefulset", "replicaset", "replicationcontroller", "job", "cronjob",
         "service", "ingress", "configmap", "secret", "persistentvolume", "persistentvolumeclaim", "pv", "pvc",
         "storageclass", "ingressclass", "networkpolicy", "serviceaccount", "clusterrole", "role", "rolebinding",
         "endpointslice", "limitrange", "resourcequota", "horizontalpodautoscaler", "hpa"}
TOOLS = {"kubectl", "kubelet", "kubeadm", "helm", "containerd", "docker", "crio", "cri-o", "podman", "etcd",
         "kustomize", "minikube", "calico", "cilium", "flannel", "coredns", "nginx", "cassandra", "redis",
         "mysql", "zookeeper", "prometheus"}
CONTRAST = [frozenset(g) for g in (
    {"foreground", "background", "orphan"}, {"hard", "soft"}, {"baseline", "restricted", "privileged"},
    {"linux", "windows"}, {"ipv4", "ipv6"}, {"ingress", "egress"}, {"required", "optional"},
    {"minimum", "maximum", "min", "max"}, {"first", "second", "last"}, {"memory", "cpu", "disk", "storage", "pid"},
    {"enable", "disable"}, {"enabled", "disabled"}, {"allow", "deny"}, {"public", "private"},
    {"namespaced", "cluster-scoped"}, {"create", "delete"}, {"worker", "control"})]


def normalize_question(text: str) -> str:
    """Key for the exact-match tier: lowercase, single spaces, no trailing punctuation."""
    return re.sub(r"\s+", " ", text.translate(_TRANS).lower()).strip(" ?.!")


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.translate(_TRANS).lower())


def _singular(word: str) -> str:
    w = word.lower()
    return w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w


@dataclass
class Signals:
    names: set
    nums: set
    versions: set
    kinds: set
    quoted: set
    contrast: list


def signals(text: str) -> Signals:
    clean_text = text.translate(_TRANS)
    toks, starts = [], []
    for m in TOKEN.finditer(clean_text):
        toks.append(m.group().strip(".:/-"))
        before = clean_text[: m.start()].rstrip()
        starts.append(not before or before[-1] in ".?!")      # first word of a sentence
    names, nums, versions, kinds = set(), set(), set(), set()
    for i, t in enumerate(toks):
        low = t.lower()
        if re.search(r"\d", t):                    # numbers and versions count even when a single digit
            versions.add(low)
            continue
        if len(t) < 2:
            continue
        sing = _singular(t)
        if sing in KINDS:
            kinds.add(sing)
        elif low in TOOLS:
            kinds.add(low)
        if "_" in t or any(c.isupper() for c in t[1:]) or (not starts[i] and t[0].isupper()):
            names.add(_squash(t))
    lows = {t.lower() for t in toks}
    clean = text.translate(_TRANS)
    quoted = {m.strip().lower() for rx in QUOTED for m in rx.findall(clean)}
    return Signals(names, nums, versions, kinds, quoted, [lows & g for g in CONTRAST])


def _present(name: str, squashed: str) -> bool:
    """Name appears in the other question, allowing a plural on either side."""
    stems = {name, name[:-1] if name.endswith("s") else name, name[:-2] if name.endswith("es") else name}
    return any(st and st in squashed for st in stems)


def _clash(x: set, y: set) -> bool:
    """Each side has something the other lacks."""
    return bool(x - y) and bool(y - x)


def entities_compatible(new_q: str, cached_q: str) -> bool:
    a, b = signals(cached_q), signals(new_q)
    if a.versions != b.versions or a.nums != b.nums:     # numbers and versions are part of the question or they are not
        return False
    if _clash(a.kinds, b.kinds) or _clash(a.quoted, b.quoted):
        return False
    if any(_clash(ga, gb) for ga, gb in zip(a.contrast, b.contrast)):
        return False
    sq_a, sq_b = _squash(cached_q), _squash(new_q)
    only_a = {n for n in a.names if not _present(n, sq_b)}
    only_b = {n for n in b.names if not _present(n, sq_a)}
    return not (only_a and only_b)
