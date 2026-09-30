#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from hades_decision.api import DecisionInput
from hades_decision.external import build_external_payload

payload = build_external_payload(
    DecisionInput(
        "do we have eggs?",
        context=("synthetic household fixture",),
        actor_class="owner",
        allowed_capability_families=("GROCY_READ",),
    ),
    ["Intent", "CapabilityFamily"],
    privacy_class="household_synthetic",
).as_dict()
assert payload["schema"] == "decision-api/v1/external"
assert "actor_class" not in payload
assert "allowed_capability_families" not in payload
assert "authorized" not in payload
assert len(payload["request_hash"]) == 64

for privacy in ("real_private", "private_finance", "authentication_state"):
    try:
        build_external_payload(DecisionInput("safe text"), ["Intent"], privacy_class=privacy)
    except ValueError:
        pass
    else:
        raise AssertionError(privacy)

try:
    build_external_payload(DecisionInput("use this api_key to login"), ["Intent"], privacy_class="public_synthetic")
except ValueError:
    pass
else:
    raise AssertionError("secret marker was not rejected")

print("PASS external Decision Plane payload strips identity and authority")
print("PASS external Decision Plane payload rejects private and secret-like input")
PY
