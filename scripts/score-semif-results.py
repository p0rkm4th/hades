#!/usr/bin/env python3
"""Score a SemIf JSONL run against the sanitized HADES corpus."""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path


def main(results_path: str) -> int:
    rows = [json.loads(line) for line in Path(results_path).read_text().splitlines() if line.strip()]
    corpus = {
        row["case_id"]: row
        for row in json.loads(Path("test-data/decision-corpus-v1/corpus.json").read_text())["cases"]
    }
    correct = 0
    brier = []
    nll = []
    latency = []
    confidence_correctness = []
    for row in rows:
        expected = corpus[row["id"]]["expected"].get("capability_family")
        if not isinstance(expected, str):
            continue
        probabilities = row["probabilities"]
        options = row["option_ids"]
        target = options.index(expected)
        prediction = max(range(len(probabilities)), key=probabilities.__getitem__)
        correct += prediction == target
        confidence_correctness.append((probabilities[prediction], prediction == target))
        brier.append(sum((p - (1 if index == target else 0)) ** 2 for index, p in enumerate(probabilities)))
        nll.append(-math.log(max(probabilities[target], 1e-12)))
        latency.append(row["total_seconds"] * 1000)
    count = len(latency)
    ordered = sorted(latency)
    ece = 0.0
    for lower in (index / 10 for index in range(10)):
        bucket = [(confidence, correct) for confidence, correct in confidence_correctness if lower <= confidence < lower + 0.1]
        if bucket:
            accuracy = sum(correct for confidence, correct in bucket) / len(bucket)
            mean_confidence = sum(confidence for confidence, correct in bucket) / len(bucket)
            ece += len(bucket) / count * abs(accuracy - mean_confidence)
    result = {
        "schema": "hades-decision-semif-score/v1",
        "cases": count,
        "correct": correct,
        "accuracy": correct / count if count else None,
        "brier": sum(brier) / count if count else None,
        "nll": sum(nll) / count if count else None,
        "ece_10_bins": ece if count else None,
        "latency_ms": {
            "p50": statistics.median(latency) if latency else None,
            "p95": ordered[max(0, int(count * 0.95) - 1)] if latency else None,
            "max": max(latency) if latency else None,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
