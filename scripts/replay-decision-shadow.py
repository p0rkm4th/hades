#!/usr/bin/env python3
"""Replay sanitized candidate results through the non-steering shadow path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hades_decision.api import DecisionInput, DecisionResult, DecisionValue
from hades_decision.current import CurrentRulesBackend
from hades_decision.shadow import ShadowDecisionPlane


class ReplayCandidate:
    name = "REPLAY_CANDIDATE"

    def __init__(self, results_path: str, corpus_path: str):
        rows = [json.loads(line) for line in Path(results_path).read_text().splitlines() if line.strip()]
        cases = {row["case_id"]: row for row in json.loads(Path(corpus_path).read_text())["cases"]}
        self.by_input = {}
        for result in rows:
            case = cases[result["id"]]
            index = max(range(len(result["probabilities"])), key=result["probabilities"].__getitem__)
            self.by_input[case["input"]] = DecisionValue(
                result["option_ids"][index],
                result["probabilities"][index],
                score_kind="candidate_probability",
                distribution=dict(zip(result["option_ids"], result["probabilities"])),
            )

    def evaluate(self, state, decision_types):
        value = self.by_input[state.request]
        decisions = {"capability_family": value} if "CapabilityFamily" in decision_types else {}
        return DecisionResult("decision-api/v1", self.name, decisions, latency_ms=None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    parser.add_argument("--corpus", default="test-data/decision-corpus-v1/corpus.json")
    args = parser.parse_args()
    corpus = json.loads(Path(args.corpus).read_text())["cases"]
    candidate = ReplayCandidate(args.results, args.corpus)
    shadow = ShadowDecisionPlane(CurrentRulesBackend(), candidate)
    agreements = disagreements = 0
    observations = []
    for case in corpus:
        if not isinstance(case.get("expected", {}).get("capability_family"), str):
            continue
        if case["input"] not in candidate.by_input:
            # Older sanitized candidate artifacts may cover the original
            # corpus slice only.  Do not fabricate candidate evidence for
            # newly added CURRENT-quality cases.
            continue
        result, observation = shadow.evaluate(
            DecisionInput(case["input"], tuple(case.get("context", []))),
            ["CapabilityFamily"],
        )
        assert result.backend == "CURRENT"
        agreements += observation.agreements
        disagreements += observation.disagreements
        observations.append(observation)
    print(json.dumps({
        "schema": "hades-decision-shadow-replay/v1",
        "candidate": candidate.name,
        "cases": len(observations),
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": agreements / len(observations) if observations else None,
        "request_hashes": [item.request_hash for item in observations],
        "raw_requests_emitted": False,
        "production_steering": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
