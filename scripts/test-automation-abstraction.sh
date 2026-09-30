#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from integrations.automation import AutomationService, AutomationSubject, InMemoryN8NGateway
from integrations.automation.contracts import AutomationError, AutomationTemplate, TemplateCatalog

gateway = InMemoryN8NGateway(
    [{
        "id": "fixture-1", "template_id": "weekly-household-summary",
        "owner": "owner", "shared_groups": ["hades-household"],
        "active": True, "trigger": "weekly", "next_run": "Sunday",
        "approved": True,
    }, {
        "id": "unrelated-1", "template_id": "arbitrary-n8n-workflow",
        "owner": "owner", "shared_groups": ["hades-household"],
        "active": True, "trigger": "manual",
    }],
    {"fixture-1": [{"startedAt": "synthetic", "status": "success"}]},
)
service = AutomationService(gateway)
owner = AutomationSubject("owner", frozenset({"hades-owner"}), owner=True)
household = AutomationSubject("household-a", frozenset({"hades-household"}))
private = AutomationSubject("household-b", frozenset())

owner_view = service.inventory(owner)
household_view = service.inventory(household)
assert len(owner_view) == len(household_view) == 1
assert "fixture-1" not in owner_view[0].public_dict()
assert owner_view[0].last_result == "success"
assert owner_view[0].approved is True
assert owner_view[0].public_dict()["approved"] is True
assert "delete" in owner_view[0].allowed_actions
assert household_view[0].allowed_actions == ("inspect", "run")
assert service.inventory(private) == ()

# Sharing a workflow is not resource authority. A shared subject sees only the
# template's household resources, never private finance or technical IDs.
assert set(household_view[0].resources) == {"grocy.household", "uptime_kuma.household", "backup.evidence"}
assert "automation_id" not in household_view[0].public_dict()

# Product approval is authoritative for control. Discovery remains visible,
# but an unapproved workflow is inspect-only until approval is recorded.
gateway.workflows[0]["approved"] = False
pending = service.inventory(owner)
assert pending[0].allowed_actions == ("inspect",)
gateway.workflows[0]["approved"] = True

preview = service.preview(owner, "weekly-household-summary", interval_minutes=10080, resources=("grocy.household", "uptime_kuma.household"))
assert preview["runner"] == "n8n" and preview["requires_confirmation"] is True
assert preview["read_only"] is True
health_preview = service.preview(owner, "server-health-watch", interval_minutes=10, resources=("hades-core.health",))
assert health_preview["read_only"] is True
assert health_preview["resources"] == ["hades-core.health"]
try:
    TemplateCatalog([AutomationTemplate(
        "invalid", "Invalid", "test", ("interval",), ("finance.private",), True,
        5, 10, ("hades-owner",), "state_change", "fail_closed",
    )])
except AutomationError:
    pass
else:
    raise AssertionError("unsupported read-only resource escaped catalog validation")
try:
    service.control(household, "fixture-1", "run", confirmed=False)
except AutomationError:
    pass
else:
    raise AssertionError("unconfirmed automation run accepted")

assert service.control(household, "fixture-1", "run", confirmed=True)["status"] == "queued"
assert service.control(owner, "fixture-1", "pause", confirmed=True)["active"] is False
assert service.control(owner, "fixture-1", "resume", confirmed=True)["active"] is True
try:
    service.preview(owner, "weekly-household-summary", interval_minutes=1, resources=("grocy.household",))
except AutomationError:
    pass
else:
    raise AssertionError("out-of-range interval accepted")

try:
    service.preview(household, "weekly-household-summary", interval_minutes=10080,
                    resources=("finance.private",))
except AutomationError:
    pass
else:
    raise AssertionError("private resource escaped template allowlist")

# Revocation is evaluated against the current subject at operation time, not
# against a cached recommendation.
revoked = AutomationSubject("household-a", frozenset())
assert service.inventory(revoked) == ()
try:
    service.control(revoked, "fixture-1", "run", confirmed=True)
except AutomationError:
    pass
else:
    raise AssertionError("revoked subject controlled automation")
print("PASS n8n-backed automation inventory hides technical IDs")
print("PASS operation-time sharing and owner controls are bounded")
print("PASS read-only template preview requires confirmation and allowlisted resources")
print("PASS revoked sharing cannot use a stale automation view")
print("PASS unrelated n8n workflows are ignored and approval state is explicit")
print("PASS control actions require confirmation and fresh authorization")
PY
