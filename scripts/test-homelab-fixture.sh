#!/usr/bin/env bash
set -euo pipefail

# Disposable read-only homelab contract fixture. It starts three synthetic
# HTTP authorities on an ephemeral loopback port and never contacts a real
# endpoint.
python - <<'PY'
import json
import importlib.util
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location(
    "homelab_reconcile", "integrations/homelab-readonly/reconcile.py"
)
reconcile = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reconcile
spec.loader.exec_module(reconcile)

now = datetime.now(timezone.utc)
state = {
    "/proxmox/api2/json/cluster/resources": {"data": [
        {"type": "node", "node": "Alexandra", "status": "online"},
        {"type": "node", "node": "Beta", "status": "degraded"},
        {"type": "qemu", "vmid": 101, "name": "dinner-app", "node": "Alexandra", "status": "running"},
        {"type": "lxc", "vmid": 102, "name": "archive", "node": "Beta", "status": "stopped"},
    ]},
    "/netbox/api/dcim/devices/?name=dinner-app": {"results": [
        {"name": "dinner-app", "status": "active", "site": "Kitchen Lab", "planned_node": "Beta", "primary_ip": "192.0.2.44"},
        {"name": "inventory-only", "status": "active", "site": "Kitchen Lab", "planned_node": "Beta", "primary_ip": "192.0.2.45"},
    ]},
    "/kuma/api/status-page/lab": {"monitors": [
        {"name": "dinner-app", "status": "down", "last_updated": (now - timedelta(minutes=10)).isoformat()},
        {"name": "archive", "status": "up", "last_updated": (now - timedelta(minutes=1)).isoformat()},
    ]},
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = state.get(self.path)
        if body is None:
            self.send_error(404)
            return
        encoded = json.dumps(body).encode()
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

def get(path):
    with urlopen(f"http://127.0.0.1:{server.server_port}{path}", timeout=5) as response:
        return json.load(response)

resources = get("/proxmox/api2/json/cluster/resources")["data"]
devices = get("/netbox/api/dcim/devices/?name=dinner-app")["results"]
monitors = get("/kuma/api/status-page/lab")["monitors"]
summary = reconcile.summarize(
    {"data": resources}, {"results": devices}, {"monitors": monitors}, now=now
)
resource = next(row for row in summary["resources"] if row["name"] == "dinner-app")
assert summary["authority"] == {
    "runtime": "Proxmox",
    "inventory": "NetBox",
    "availability": "Uptime Kuma",
}
assert resource["runtime"]["node"] == "Alexandra"
assert resource["runtime_status"] == "running"
assert resource["currently_online"] is True
assert resource["inventory"]["planned_node"] == "Beta"
assert resource["inventory"]["primary_ip"] == "192.0.2.44"
assert resource["availability"]["status"] == "down"
assert resource["availability_freshness"] == "STALE"
assert resource["conflicts"]
inventory_only = next(row for row in summary["resources"] if row["name"] == "inventory-only")
assert inventory_only["runtime_status"] == "NOT_OBSERVED"
assert inventory_only["currently_online"] is False
assert inventory_only["inventory"]["primary_ip"] == "192.0.2.45"
assert "inventory-only" in summary["inventory_only_names"]
archive = next(row for row in summary["resources"] if row["name"] == "archive")
assert archive["availability"]["status"] == "up"
assert archive["availability_freshness"] == "FRESH"
assert archive["runtime_status"] == "stopped"
assert archive["currently_online"] is False
nodes = {row["node"]: row for row in resources if row["type"] == "node"}
guests = {row["name"]: row for row in resources if row["type"] in {"qemu", "lxc"}}

assert nodes["Alexandra"]["status"] == "online"
assert nodes["Beta"]["status"] == "degraded"
assert next(row for row in summary["resources"] if row["name"] == "Beta")["currently_online"] is False
assert guests["dinner-app"]["node"] == "Alexandra"
assert guests["dinner-app"]["status"] == "running"
assert guests["archive"]["status"] == "stopped"
assert devices[0]["planned_node"] == "Beta"
assert guests["dinner-app"]["node"] != devices[0]["planned_node"]
monitor = monitors[0]
assert monitor["status"] == "down"
assert now - datetime.fromisoformat(monitor["last_updated"]) > timedelta(minutes=5)
fresh_monitor = monitors[1]
assert now - datetime.fromisoformat(fresh_monitor["last_updated"]) < timedelta(minutes=5)

try:
    urlopen(Request(f"http://127.0.0.1:{server.server_port}/proxmox/api2/json/cluster/resources", method="POST"), timeout=5)
except HTTPError as exc:
    assert exc.code == 405
else:
    raise AssertionError("synthetic homelab fixture accepted a write")

server.shutdown()
print("PASS Proxmox runtime authority fixture")
print("PASS NetBox intended-inventory contradiction fixture")
print("PASS Uptime Kuma stale-observation fixture")
print("PASS synthetic homelab is read-only")
PY
