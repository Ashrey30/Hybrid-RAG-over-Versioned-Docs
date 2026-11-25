"""One-off cleanup of data/cache_pairs.jsonl after hand review: drop 4 weak pairs, replace 6 weak near-misses.
Each rule matches exactly one question by its opening words; the script stops if a rule matches 0 or 2+ rows.
Run: python scripts/fix_cache_pairs.py
"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "cache_pairs.jsonl"

DROP = [
    "Why does creating the second pod in the `quota-mem-cpu-example`",
    "If a node is frequently toggling its pressure condition",
    'What metric type is used for the Kubernetes metric named "endpoint_slice_controller_changes"',
    "In the RequestedToCapacityRatio",
]
REPLACE = {
    "What RestartPolicy must be set for a pod template in a DaemonSet":
        "What RestartPolicy must be set for a pod template in a Job, and what is the default if it is not specified?",
    "How can I switch a Kubernetes node from Docker Engine to containerd":
        "How can I switch a Kubernetes node from Docker Engine to CRI-O as the container runtime using kubeadm?",
    "Do I need to manually enable the CustomResourceFieldSelectors":
        "Do I need to manually enable the CustomResourceFieldSelectors feature gate on Kubernetes v1.30 to use selectable fields in a CustomResourceDefinition?",
    "In the latest kubeadm JoinConfiguration example for a worker node":
        "In the latest kubeadm JoinConfiguration example for a control plane node, how is the node-ip extra argument specified under nodeRegistration?",
    "How can I designate a default IngressClass":
        "How can I designate a default StorageClass in my Kubernetes cluster, and what occurs if more than one StorageClass is marked as default?",
    "What is the purpose of the Job object":
        "What is the purpose of the CronJob object and what types of work items can it handle?",
}


def find(rows, prefix):
    hits = [i for i, r in enumerate(rows) if r["question"].startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"rule {prefix!r} matched {len(hits)} rows; expected exactly 1")
    return hits[0]


def main() -> None:
    rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    n0 = len(rows)
    for prefix, new in REPLACE.items():
        rows[find(rows, prefix)]["near_miss"] = new
    for prefix in DROP:
        rows.pop(find(rows, prefix))
    PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"{n0} pairs -> {len(rows)} pairs ({len(REPLACE)} near-misses replaced, {len(DROP)} dropped)")


if __name__ == "__main__":
    main()
