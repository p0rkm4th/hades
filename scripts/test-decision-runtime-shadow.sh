#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from hades_decision.api import DecisionInput, DecisionResult, DecisionValue, DECISION_SCHEMA
from hades_decision.current import CurrentRulesBackend
from hades_decision.runtime import RuntimeShadow, ShadowRuntimeConfig

class Candidate:
    name = "SYNTHETIC_RUNTIME_CANDIDATE"
    def evaluate(self, state, decision_types):
        return DecisionResult(
            DECISION_SCHEMA,
            self.name,
            {"intent": DecisionValue("wrong", 0.5)},
            latency_ms=1.0,
        )

seen = []
runtime = RuntimeShadow(
    CurrentRulesBackend(), Candidate(),
    ShadowRuntimeConfig(enabled=True, sample_rate=1.0),
    emit=seen.append,
)
result = runtime.evaluate(DecisionInput("hey"), ["Intent"])
assert result.backend == "CURRENT"
assert result.decisions["intent"].value == "general_chat"
assert seen and seen[0].candidate_backend == "SYNTHETIC_RUNTIME_CANDIDATE"

disabled = RuntimeShadow(
    CurrentRulesBackend(), Candidate(),
    ShadowRuntimeConfig(enabled=False, sample_rate=1.0),
    emit=seen.append,
)
before = len(seen)
assert disabled.evaluate(DecisionInput("hey"), ["Intent"]).backend == "CURRENT"
assert len(seen) == before

try:
    RuntimeShadow(CurrentRulesBackend(), Candidate(), ShadowRuntimeConfig(production_steering=True))
except ValueError:
    pass
else:
    raise AssertionError("steering flag was accepted")
print("PASS runtime shadow hook is feature-flagged and non-steering")
print("PASS disabled runtime shadow produces no candidate observation")
PY
