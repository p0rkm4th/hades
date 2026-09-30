#!/usr/bin/env python3
"""Measure the production CURRENT semantic signals on the sanitized corpus."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from hades_decision.api import DecisionInput
from hades_decision.current import CurrentRulesBackend


def main(path: str) -> int:
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    backend = CurrentRulesBackend()
    cases = corpus["cases"]
    latencies = []
    totals = {"intent": 0, "capability_family": 0, "tool_family": 0, "needs_clarification": 0, "reasoning_tier": 0}
    correct = {key: 0 for key in totals}
    rows = []
    names = {"intent": "Intent", "capability_family": "CapabilityFamily", "tool_family": "ToolFamily", "needs_clarification": "NeedsClarification", "reasoning_tier": "ReasoningTier"}
    for case in cases:
        expected = case.get("expected", {})
        requested = [names[key] for key in totals if key in expected]
        state = DecisionInput(
            request=case["input"], context=tuple(case.get("context", [])),
            actor_class=case.get("actor_class", "unknown"), input_kind=case.get("input_kind", "typed"),
        )
        started = time.perf_counter()
        result = backend.evaluate(state, requested)
        elapsed = (time.perf_counter() - started) * 1000
        latencies.append(elapsed)
        for key in totals:
            if key in expected and isinstance(expected[key], list):
                actual = list(result.recommendations.get(key, ()))
                totals[key] += 1
                if actual == expected[key]:
                    correct[key] += 1
                continue
            if key in expected and key in result.decisions:
                totals[key] += 1
                actual = result.decisions[key].value
                target = str(expected[key]).lower() if isinstance(expected[key], bool) else expected[key]
                if actual == target:
                    correct[key] += 1
        rows.append({"case_id": case["case_id"], "result": result.as_dict()})
    metrics = {
        key: {"correct": correct[key], "cases": totals[key], "accuracy": (correct[key] / totals[key] if totals[key] else None)}
        for key in totals
    }
    ordered = sorted(latencies)
    print(json.dumps({
        "schema": "hades-decision-benchmark/v1", "backend": backend.manifest,
        "corpus": corpus["schema"], "cases": len(cases), "metrics": metrics,
        "latency_ms": {"p50": statistics.median(latencies) if latencies else None,
                        "p95": ordered[max(0, int(len(ordered) * 0.95) - 1)] if ordered else None,
                        "max": max(latencies) if latencies else None},
        "rows": rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test-data/decision-corpus-v1/corpus.json"))
