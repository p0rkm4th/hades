#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from hades_decision.api import (
    DECISION_SCHEMA,
    DecisionInput,
    DecisionPlane,
    DecisionResult,
    intersect_recommended_capabilities,
)
from hades_decision.current import CurrentRulesBackend

class BrokenBackend:
    name = "BROKEN"
    manifest = {"supported_decisions": []}
    def evaluate(self, *_):
        raise RuntimeError("synthetic backend outage")

current = CurrentRulesBackend()
plane = DecisionPlane(BrokenBackend(), current)
result = plane.evaluate(DecisionInput("do we have eggs?"), ["Intent", "CapabilityFamily", "ToolRequired", "ToolFamily"])
assert result.schema == DECISION_SCHEMA
assert result.backend == "CURRENT"
assert result.fallback == "current"
assert result.decisions["intent"].value == "pantry_read"
assert result.decisions["tool_family"].value == "GROCY_READ"

for request, intent, family, tool in [
    ("hey", "general_chat", "GENERAL", "NONE"),
    ("look up Python", "web_search", "WEB", "WEB_SEARCH"),
    ("read the first result", "page_read", "WEB", "PAGE_READ"),
    ("remember my test color is cobalt", "memory", "MEMORY", "MEMORY"),
    ("restart the other server", "homelab", "HOMELAB", "HOMELAB_READ"),
    ("show me the private checking account", "finance", "FINANCE", "FINANCE"),
]:
    got = current.evaluate(DecisionInput(request), ["Intent", "CapabilityFamily", "ToolFamily"])
    assert got.decisions["intent"].value == intent, (request, got.as_dict())
    assert got.decisions["capability_family"].value == family, (request, got.as_dict())
    assert got.decisions["tool_family"].value == tool, (request, got.as_dict())

ambiguous = current.evaluate(DecisionInput("restart it"), ["NeedsClarification", "CapabilityFamily"])
assert ambiguous.decisions["needs_clarification"].value == "true"

composite = current.evaluate(
    DecisionInput("what groceries are low and is Minecraft running?"),
    ["CapabilityFamily", "ToolFamily"],
)
assert composite.recommendations == {
    "capability_family": ("GROCY", "SELF_SERVICE"),
    "tool_family": ("GROCY_READ", "HOMELAB_READ"),
}

# Recommendation cannot grant authority: the API carries actor class and
# optional capability context only as bounded input; it has no allow/deny
# result and no execution surface.
assert not hasattr(result, "authorized")
assert not hasattr(result, "execute")
assert intersect_recommended_capabilities(
    ("GROCY_READ", "WEB_SEARCH"),
    ("GROCY_READ", "HOMELAB_WRITE", "WEB_SEARCH"),
) == ("GROCY_READ", "WEB_SEARCH")
assert intersect_recommended_capabilities((), ("HOMELAB_WRITE",)) == ()
print("PASS decision-api/v1 schema and CURRENT fallback")
print("PASS CURRENT routing control covers ordinary/domain decisions")
print("PASS recommended capabilities cannot expand deterministic authorization")
print("PASS decision recommendation has no authority or execution surface")
print("PASS composite recommendations remain semantic and authority-free")
PY
