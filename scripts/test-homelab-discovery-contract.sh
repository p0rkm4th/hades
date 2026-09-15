#!/usr/bin/env bash
set -euo pipefail

# Disposable Nmap-shaped discovery fixture.  It never invokes a scanner,
# contacts a real network, or writes inventory.
python3 - <<'PY'
import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

allowed = [ipaddress.ip_network("192.0.2.0/29")]
state = {
    "/scan": {
        "source": "nmap.synthetic",
        "target": "192.0.2.0/29",
        "retrieved_at": "2026-09-14T12:00:00Z",
        "hosts": [
            {"ip": "192.0.2.2", "hostname": "router-synthetic", "ports": [53, 80]},
            {"ip": "192.0.2.3", "hostname": "dinner-app", "ports": [443]},
        ],
    },
    "/netbox/api/dcim/devices/": {
        "results": [{"name": "dinner-app", "planned_ip": "192.0.2.4"}]
    },
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

    def do_POST(self):
        self.send_error(405)

    def do_PUT(self):
        self.send_error(405)

    def do_DELETE(self):
        self.send_error(405)

    def log_message(self, *_args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

def get(path):
    with urlopen(f"http://127.0.0.1:{server.server_port}{path}", timeout=5) as response:
        return json.load(response)

scan = get("/scan")
target = ipaddress.ip_network(scan["target"])
assert any(target.subnet_of(network) for network in allowed)
assert all(
    any(ipaddress.ip_address(host["ip"]) in network for network in allowed)
    for host in scan["hosts"]
)
assert scan["hosts"][1]["hostname"] == "dinner-app"
assert 443 in scan["hosts"][1]["ports"]

inventory = get("/netbox/api/dcim/devices/")["results"]
assert inventory[0]["planned_ip"] != scan["hosts"][1]["ip"]
assert inventory[0]["planned_ip"] == "192.0.2.4"

try:
    urlopen(
        Request(
            f"http://127.0.0.1:{server.server_port}/netbox/api/dcim/devices/",
            data=json.dumps(scan["hosts"][1]).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        ),
        timeout=5,
    )
except HTTPError as exc:
    assert exc.code == 405
else:
    raise AssertionError("discovery fixture accepted an inventory write")

try:
    external = ipaddress.ip_network("198.51.100.0/24")
    assert any(external.subnet_of(network) for network in allowed)
except AssertionError:
    pass
else:
    raise AssertionError("out-of-scope scan target accepted")

server.shutdown()
print("PASS bounded synthetic network discovery evidence")
print("PASS discovery does not silently alter NetBox inventory")
print("PASS out-of-scope scan target rejected")
PY
