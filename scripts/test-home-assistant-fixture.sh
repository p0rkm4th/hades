#!/usr/bin/env bash
set -euo pipefail

# Disposable Home Assistant-shaped REST fixture. It exercises only selected
# read entities and proves excluded security entities and writes are rejected.
python - <<'PY'
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

now = datetime.now(timezone.utc)
states = {
    "light.living_room": {"state": "on", "last_changed": now.isoformat()},
    "sensor.apartment_temperature": {"state": "21.5", "last_changed": now.isoformat()},
    "fan.air_purifier": {"state": "on", "last_changed": now.isoformat()},
    "sensor.bedroom": {"state": "unavailable", "last_changed": (now - timedelta(minutes=10)).isoformat()},
    "lock.front_door": {"state": "locked", "last_changed": now.isoformat()},
    "camera.entryway": {"state": "idle", "last_changed": now.isoformat()},
}
requested = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        prefix = "/api/states/"
        if not self.path.startswith(prefix):
            self.send_error(404)
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
allowed = {"light.living_room", "sensor.apartment_temperature", "fan.air_purifier", "sensor.bedroom"}
excluded = {"lock.front_door", "camera.entryway"}

def read(entity):
    if entity not in allowed:
        raise PermissionError(f"entity excluded by read-only allowlist: {entity}")
    with urlopen(f"{base}/api/states/{entity}", timeout=5) as response:
        return json.load(response)

assert read("light.living_room")["state"] == "on"
assert read("sensor.apartment_temperature")["state"] == "21.5"
assert read("fan.air_purifier")["state"] == "on"
bedroom = read("sensor.bedroom")
assert bedroom["state"] == "unavailable"
assert now - datetime.fromisoformat(bedroom["last_changed"]) > timedelta(minutes=5)
for entity in excluded:
    try:
        read(entity)
    except PermissionError:
        pass
    else:
        raise AssertionError("security-sensitive entity bypassed allowlist")
assert not excluded.intersection(requested)

try:
    urlopen(Request(f"{base}/api/states/light.living_room", method="POST"), timeout=5)
except HTTPError as exc:
    assert exc.code == 405
else:
    raise AssertionError("synthetic Home Assistant fixture accepted a write")

server.shutdown()
print("PASS Home Assistant selected ordinary-entity fixture")
print("PASS Home Assistant unavailable/stale entity fixture")
print("PASS Home Assistant security-sensitive allowlist fixture")
print("PASS synthetic Home Assistant is read-only")
PY
