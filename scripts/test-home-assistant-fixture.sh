#!/usr/bin/env bash
set -euo pipefail

# Disposable Home Assistant-shaped REST fixture. It exercises only selected
# read entities and proves excluded security entities and writes are rejected.
python - <<'PY'
import json
import os
import sys
import tempfile
import threading
import types
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

now = datetime.now(timezone.utc)
states = {
    "light.living_room": {"state": "on", "last_updated": now.isoformat()},
    "sensor.apartment_temperature": {"state": "21.5", "last_updated": now.isoformat()},
    "fan.air_purifier": {"state": "on", "last_updated": now.isoformat()},
    "sensor.bedroom": {"state": "unavailable", "last_updated": (now - timedelta(minutes=10)).isoformat()},
    "lock.front_door": {"state": "locked", "last_updated": now.isoformat()},
    "cover.garage_door": {"state": "closed", "last_updated": now.isoformat()},
    "alarm_control_panel.home": {"state": "armed_away", "last_updated": now.isoformat()},
    "camera.entryway": {"state": "idle", "last_updated": now.isoformat()},
}
requested = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        prefix = "/api/states/"
        if not self.path.startswith(prefix):
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer synthetic-ha-token":
            self.send_error(401)
            return
        entity = self.path[len(prefix):]
        requested.append(entity)
        value = states.get(entity)
        if value is None:
            self.send_error(404)
            return
        encoded = json.dumps({"entity_id": entity, **value}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self): self.send_error(405)
    def do_PUT(self): self.send_error(405)
    def do_DELETE(self): self.send_error(405)
    def log_message(self, *_args): pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"
token_file = tempfile.NamedTemporaryFile(prefix="hades-ha-token-", delete=False)
token_file.write(b"synthetic-ha-token\n")
token_file.close()
os.chmod(token_file.name, 0o600)
sys.path.insert(0, "integrations/home-assistant-readonly")
os.environ["HADES_HOME_ASSISTANT_URL"] = base
os.environ["HADES_HOME_ASSISTANT_TOKEN_FILE"] = token_file.name
os.environ["HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST"] = ",".join([
    "light.living_room", "sensor.apartment_temperature", "fan.air_purifier", "sensor.bedroom"
])
# Keep this fixture runnable on the dependency-free contract runner. The
# adapter's HTTP/policy functions are exercised; stdio transport is not.
sys.modules["anyio"] = types.ModuleType("anyio")
mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = object
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = object
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, type(name, (), {"__init__": lambda self, *args, **kwargs: None}))
sys.modules.update({"mcp": types.ModuleType("mcp"), "mcp.server": mcp_server,
                    "mcp.server.lowlevel": mcp_lowlevel, "mcp.server.stdio": mcp_stdio,
                    "mcp.types": mcp_types})
import server as adapter
allowed = {"light.living_room", "sensor.apartment_temperature", "fan.air_purifier", "sensor.bedroom"}
excluded = {"lock.front_door", "cover.garage_door", "alarm_control_panel.home", "camera.entryway"}

def read(entity):
    if entity not in allowed:
        raise PermissionError(f"entity excluded by read-only allowlist: {entity}")
    request = Request(
        f"{base}/api/states/{entity}",
        headers={"Authorization": "Bearer synthetic-ha-token"},
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)

assert read("light.living_room")["state"] == "on"
assert read("sensor.apartment_temperature")["state"] == "21.5"
assert read("fan.air_purifier")["state"] == "on"
bedroom = read("sensor.bedroom")
assert bedroom["state"] == "unavailable"
assert now - datetime.fromisoformat(bedroom["last_updated"]) > timedelta(minutes=5)
for entity in excluded:
    try:
        read(entity)
    except PermissionError:
        pass
    else:
        raise AssertionError("security-sensitive entity bypassed allowlist")
assert not excluded.intersection(requested)

requested.clear()
shaped = adapter.read_entity("light.living_room")
assert shaped["status"] == "OK" and shaped["result"]["source"] == "Home Assistant"
assert shaped["result"]["state"] == "on"
selected = adapter.read_selected()
assert selected["status"] == "OK" and len(selected["results"]) == 4
assert any(item["result"]["state"] == "unavailable" and item["result"]["freshness"] == "STALE" for item in selected["results"])
denied = adapter.read_entity("lock.front_door")
assert denied["status"] == "FAILED"
for entity in ("cover.garage_door", "alarm_control_panel.home", "camera.entryway"):
    assert adapter.read_entity(entity)["status"] == "FAILED"
assert not excluded.intersection(requested)

with open(token_file.name, "w", encoding="utf-8") as handle:
    handle.write("wrong-token\n")
os.chmod(token_file.name, 0o600)
assert adapter.read_entity("light.living_room")["status"] == "FAILED"
with open(token_file.name, "w", encoding="utf-8") as handle:
    handle.write("synthetic-ha-token\n")
os.chmod(token_file.name, 0o600)

try:
    urlopen(Request(
        f"{base}/api/states/light.living_room",
        headers={"Authorization": "Bearer synthetic-ha-token"},
        method="POST",
    ), timeout=5)
except HTTPError as exc:
    assert exc.code == 405
else:
    raise AssertionError("synthetic Home Assistant fixture accepted a write")

server.shutdown()
os.unlink(token_file.name)
print("PASS Home Assistant selected ordinary-entity fixture")
print("PASS Home Assistant unavailable/stale entity fixture")
print("PASS Home Assistant security-sensitive allowlist fixture")
print("PASS synthetic Home Assistant is read-only")
PY
