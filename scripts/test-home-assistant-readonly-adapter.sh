#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import importlib.util
import sys
from datetime import datetime, timedelta, timezone

root = sys.argv[1]
spec = importlib.util.spec_from_file_location("ha_policy", root + "/integrations/home-assistant-readonly/policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

assert policy.validate_allowlist(["light.living_room", "sensor.apartment_temperature", "light.living_room"]) == ["light.living_room", "sensor.apartment_temperature"]
for blocked in ("lock.front_door", "cover.garage_door", "alarm_control_panel.home", "camera.entryway", "door_access.front"):
    try:
        policy.validate_allowlist([blocked])
    except ValueError:
        pass
    else:
        raise AssertionError(blocked)
now = datetime(2026, 9, 14, tzinfo=timezone.utc)
assert policy.shape_state({"entity_id": "light.living_room", "state": "on", "attributes": {}, "last_updated": "2026-09-13T23:00:00Z"}, now=now)["freshness"] == "STALE"
assert policy.shape_state({"entity_id": "sensor.x", "state": "unavailable", "attributes": {}}, now=now)["state"] == "unavailable"
print("PASS Home Assistant read-only policy and state contract")
PY

python3 -m py_compile "$repo_dir/integrations/home-assistant-readonly/policy.py" "$repo_dir/integrations/home-assistant-readonly/server.py"
