#!/usr/bin/env python3
"""Export the sanitized corpus to SemIf's typed-option input shape."""

from __future__ import annotations

import json
from pathlib import Path


OPTIONS = [
    ("GENERAL", "ordinary conversation without an integration"),
    ("GROCY", "pantry, groceries, recipes, or household inventory"),
    ("WEB", "web search or reading a web page"),
    ("MEMORY", "the actor's own remembered preferences or facts"),
    ("FINANCE", "finance, budget, account, or spending information"),
    ("HOMELAB", "status or read-only information about infrastructure"),
    ("SELF_SERVICE", "an approved personal server or workload"),
    ("AGENT_ZERO", "a bounded operator or Agent Zero request"),
    ("HOME_ASSISTANT", "read-only household sensor or home state"),
]


def main() -> None:
    corpus = json.loads(Path("test-data/decision-corpus-v1/corpus.json").read_text())
    for case in corpus["cases"]:
        expected = case.get("expected", {}).get("capability_family")
        if not isinstance(expected, str):
            continue
        state = " ".join([*case.get("context", []), case["input"]]).strip()
        print(json.dumps({
            "id": case["case_id"],
            "state": state,
            "question": "Which HADES capability family best fits this request?",
            "options": [{"id": key, "description": description} for key, description in OPTIONS],
            "expected": expected,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
