#!/usr/bin/env python3
"""Synthetic contract for the aggregate-only Hindsight read helper."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


path = Path(__file__).with_name("hindsight-aggregate-stats.py")
spec = importlib.util.spec_from_file_location("hindsight_aggregate_stats", path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

bank_ids = ["synthetic-alpha-bank-private-id", "synthetic-beta-bank-private-id"]
counts = {
    bank_ids[0]: {"pending_operations": 2, "failed_operations": 7, "pending_consolidation": 3, "failed_consolidation": 4},
    bank_ids[1]: {"pending_operations": 5, "failed_operations": 11, "pending_consolidation": 13, "failed_consolidation": 17},
}
requests: list[str] = []
malformed_stats = False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        if self.path == "/v1/default/banks":
            payload = {"banks": [{"bank_id": value, "name": f"PRIVATE {value}"} for value in bank_ids]}
        else:
            bank_id = self.path.removeprefix("/v1/default/banks/").removesuffix("/stats")
            payload = counts.get(bank_id, {})
            if malformed_stats and isinstance(payload, dict):
                payload = {key: value for key, value in payload.items() if key != "failed_consolidation"}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    base = f"http://127.0.0.1:{server.server_port}"
    bank_count, totals = module.aggregate(base)
    assert bank_count == 2, bank_count
    assert totals == {
        "pending_operations": 7,
        "failed_operations": 18,
        "pending_consolidation": 16,
        "failed_consolidation": 21,
    }, totals
    assert len(requests) == 3 and requests[0] == "/v1/default/banks", requests
    assert all(request.endswith("/stats") for request in requests[1:]), requests
    assert not any("/operations" in request or "memories" in request for request in requests)
    for unsafe_url in (
        "http://192.0.2.1:8888",
        "https://127.0.0.1:8888",
        "http://user:secret@127.0.0.1:8888",
        "http://localhost:8888",
    ):
        try:
            module.aggregate(unsafe_url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe base URL was accepted: {unsafe_url.split('@')[-1]}")
    assert len(requests) == 3, requests

    result = subprocess.run(
        [sys.executable, str(path), "--base-url", base],
        check=False, capture_output=True, text=True,
    )
    rendered = result.stdout
    assert result.returncode == 0, result.stderr
    assert "banks=2" in rendered and "failed_operations=18" in rendered, rendered
    assert all(private not in rendered for private in bank_ids), rendered
    assert "PRIVATE" not in rendered, rendered

    malformed_stats = True
    try:
        module.aggregate(base)
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete per-bank stats were accepted")
    malformed_stats = False
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

print("PASS aggregate helper reads only bank list and per-bank stats over loopback")
print("PASS aggregate output contains counts only and omits bank identifiers/names")
