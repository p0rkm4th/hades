#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
import tempfile
from concurrent.futures import ThreadPoolExecutor

from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3Catalog,
    Phase3DuplicateError,
    Phase3Quotas,
    Phase3QuotaError,
    Phase3Service,
    Phase3Store,
    Phase3AuthorizationError,
)

path = tempfile.mktemp(prefix="hades-phase3-")
catalog = Phase3Catalog({"hades-core": "HADES Core", "minecraft-night": "Minecraft Night"})
service = Phase3Service(Phase3Store(path), catalog=catalog, quotas=Phase3Quotas(household_active=2))
a = Phase3Authority("household-a", "household", frozenset({"hades-core.health", "grocy.household"}))
b = Phase3Authority("household-b", "household", frozenset({"grocy.household"}))
owner = Phase3Authority("owner", "owner", frozenset({"hades-core.health", "grocy.household", "backup.evidence"}))

assert [item["template"] for item in service.catalog.entries(a)] == [
    "server-health-watch", "low-inventory-summary", "weekly-household-summary"
]
assert [item["template"] for item in service.catalog.entries(b)] == [
    "low-inventory-summary", "weekly-household-summary"
]
try:
    service.preview(b, "server-health-watch", {"resource_id": "hades-core", "interval_minutes": 10})
except Phase3AuthorizationError:
    pass
else:
    raise AssertionError("B received an unauthorized server resource")
for bad_payload in (
    {"resource_id": "hades-core", "interval_minutes": 10, "n8n_json": {"nodes": []}},
    {"resource_scope": ["private.finance"], "interval_minutes": 10080},
):
    try:
        service.preview(owner if "private.finance" in bad_payload.get("resource_scope", []) else a, "weekly-household-summary" if "resource_scope" in bad_payload else "server-health-watch", bad_payload)
    except Exception:
        pass
    else:
        raise AssertionError("unsupported or unapproved template configuration was admitted")

preview = service.preview(a, "server-health-watch", {"resource_id": "hades-core", "interval_minutes": 10})
created = service.confirm(a, preview["preview_id"], preview["preview_hash"], "create:" + preview["preview_id"])
assert created["creator_subject_id"] == "household-a" == created["owner_subject_id"]
duplicate = service.preview(a, "server-health-watch", {"resource_id": "hades-core", "interval_minutes": 10})
try:
    service.confirm(a, duplicate["preview_id"], "stale-preview-hash", "stale-confirm")
except Exception:
    pass
else:
    raise AssertionError("stale preview hash was accepted")
try:
    service.confirm(a, duplicate["preview_id"], duplicate["preview_hash"], "duplicate")
except Phase3DuplicateError:
    pass
else:
    raise AssertionError("duplicate automation was admitted")

# A retry with the same request key reconciles to the one canonical record.
retry_payload = dict(created)
assert service.store.create(a, retry_payload, Phase3Quotas(), "create:" + preview["preview_id"])["automation_id"] == created["automation_id"]

other = Phase3Authority("household-other", "household", frozenset({"hades-core.health"}))
try:
    service.confirm(other, duplicate["preview_id"], duplicate["preview_hash"], "cross-user-confirm")
except Exception:
    pass
else:
    raise AssertionError("cross-user confirmation reused another actor's preview")

try:
    service.store.share(a, created["automation_id"], b)
except Phase3AuthorizationError:
    pass
else:
    raise AssertionError("sharing granted a resource B does not possess")

low = service.preview(a, "low-inventory-summary", {})
low_item = service.confirm(a, low["preview_id"], low["preview_hash"], "create:" + low["preview_id"])
service.store.share(a, low_item["automation_id"], b)
service.control(b, low_item["automation_id"], "run")
service.control(b, low_item["automation_id"], "run")
try:
    service.control(b, low_item["automation_id"], "run")
except Phase3QuotaError:
    pass
else:
    raise AssertionError("manual run bound was bypassed")
for action in ("pause", "delete"):
    try:
        service.control(b, low_item["automation_id"], action)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError(f"shared recipient controlled automation with {action}")

try:
    service.control(a, created["automation_id"], "edit", interval_minutes=2)
except Exception:
    pass
else:
    raise AssertionError("pathological interval was admitted")

service.store.revoke_resource("household-a", "hades-core.health")
try:
    revoked_a = Phase3Authority("household-a", "household", frozenset({"grocy.household"}))
    service.control(revoked_a, created["automation_id"], "run")
except Phase3AuthorizationError:
    pass
else:
    raise AssertionError("revoked resource remained executable")

# Identity removal disables owned records and removes that actor from shares;
# metadata remains available for bounded owner/admin cleanup.
service.store.revoke_actor("household-a", "synthetic identity removal")
assert service.store.get(created["automation_id"])["status"] == "AUTHORIZATION_LOST"
assert service.store.get(low_item["automation_id"])["shared_with"] == []
assert service.store.list_owned("household-a")
inactive = Phase3Authority("household-a", "household", frozenset({"grocy.household"}), active=False)
assert service.store.list_for(inactive) == []
try:
    service.control(inactive, low_item["automation_id"], "run")
except Exception:
    pass
else:
    raise AssertionError("inactive identity retained execution authority")
try:
    service.confirm(Phase3Authority("household-a", "household", frozenset()), duplicate["preview_id"], duplicate["preview_hash"], "revoked-confirm")
except Exception:
    pass
else:
    raise AssertionError("revoked authority confirmed a staged preview")

quota_service = Phase3Service(
    Phase3Store(tempfile.mktemp(prefix="hades-phase3-quota-")),
    catalog=Phase3Catalog({"hades-core": "HADES Core", "minecraft-night": "Minecraft Night", "tartarus": "Tartarus"}),
    quotas=Phase3Quotas(household_active=2),
)
quota_actor = Phase3Authority("quota-user", "household", frozenset({"hades-core.health", "minecraft-night.health", "tartarus.health"}))
for resource in ("hades-core", "minecraft-night"):
    preview = quota_service.preview(quota_actor, "server-health-watch", {"resource_id": resource, "interval_minutes": 10})
    quota_service.confirm(quota_actor, preview["preview_id"], preview["preview_hash"], "q-" + resource)
try:
    preview = quota_service.preview(quota_actor, "server-health-watch", {"resource_id": "tartarus", "interval_minutes": 10})
    quota_service.confirm(quota_actor, preview["preview_id"], preview["preview_hash"], "over-quota")
except Phase3QuotaError:
    pass
else:
    raise AssertionError("household quota was bypassed")

# Two admissions racing a one-record quota cannot create two records.
race_service = Phase3Service(
    Phase3Store(tempfile.mktemp(prefix="hades-phase3-race-")),
    catalog=Phase3Catalog({"hades-core": "HADES Core", "minecraft-night": "Minecraft Night"}),
    quotas=Phase3Quotas(household_active=1),
)
race_actor = Phase3Authority("race-user", "household", frozenset({"hades-core.health", "minecraft-night.health"}))
race_previews = [race_service.preview(race_actor, "server-health-watch", {"resource_id": resource, "interval_minutes": 10}) for resource in ("hades-core", "minecraft-night")]
def admit(item):
    try:
        return race_service.confirm(race_actor, item["preview_id"], item["preview_hash"], "race:" + item["preview_id"])
    except Exception:
        return None
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(admit, race_previews))
assert len(race_service.store.list_owned("race-user")) == 1

assert service.store.admin_disable(owner, low_item["automation_id"], "synthetic owner oversight")["enabled"] is False
assert any(item["action"] == "admin-disable" for item in service.store.audit_for(low_item["automation_id"]))
print("PASS Phase 3 self-service policy, ownership, quota, revocation, sharing, and admin contracts")
PY
