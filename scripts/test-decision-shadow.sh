#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from hades_decision.api import DecisionInput, DecisionResult, DECISION_SCHEMA, DecisionValue
from hades_decision.current import CurrentRulesBackend
from hades_decision.shadow import ShadowDecisionPlane

class Candidate:
    name = "SYNTHETIC_CANDIDATE"
    def evaluate(self, state, decision_types):
        current = CurrentRulesBackend().evaluate(state, decision_types)
        decisions = dict(current.decisions)
        if "Intent" in decision_types:
            decisions["intent"] = DecisionValue("wrong_candidate_value", 0.51)
        return DecisionResult(DECISION_SCHEMA, self.name, decisions, latency_ms=1.0)

class Broken:
    name = "BROKEN_CANDIDATE"
    def evaluate(self, *_):
        raise RuntimeError("synthetic candidate failure")

current = CurrentRulesBackend()
production, observation = ShadowDecisionPlane(current, Candidate()).evaluate(
    DecisionInput("hey"), ["Intent", "CapabilityFamily"]
)
assert production.backend == "CURRENT"
assert production.decisions["intent"].value == "general_chat"
assert observation.disagreements == 1
assert len(observation.request_hash) == 64
assert "hey" not in str(observation.as_dict())

production, failed = ShadowDecisionPlane(current, Broken()).evaluate(
    DecisionInput("hey"), ["Intent"]
)
assert production.backend == "CURRENT"
assert failed.candidate_error == "RuntimeError"
print("PASS shadow candidate cannot steer CURRENT")
print("PASS shadow evidence is hashed and failure-local")
PY
