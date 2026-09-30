#!/usr/bin/env python3
"""Exercise the injected receipt apply route against a concurrent fake Grocy."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import hmac
import multiprocessing
import json
import os
import tempfile
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        return lambda function: self.routes.setdefault(path, function)

    def get(self, path):
        return lambda function: self.routes.setdefault(path, function)


class FakeRequest:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


class SyntheticGrocyHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _respond(self, value):
        payload = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        assert self.headers.get("GROCY-API-KEY") == "synthetic-grocy-key"
        with self.server.state_lock:
            self.server.writes.append((self.path, body))
        time.sleep(0.15)
        with self.server.state_lock:
            self.server.stock += float(body["amount"])
        self._respond({"ok": True})

    def do_GET(self):  # noqa: N802
        assert self.headers.get("GROCY-API-KEY") == "synthetic-grocy-key"
        with self.server.state_lock:
            stock = self.server.stock
        self._respond({"product_id": 5, "amount_aggregated": stock})


class FakeJSONResponse:
    def __init__(self, value, status_code=200):
        self.value = value
        self.status_code = status_code


class FakeHTTPException(Exception):
    pass


def load_apply_route():
    tree = ast.parse(Path("webui/receipt_upload_compat.py").read_text(encoding="utf-8"))
    route = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ROUTE" for target in node.targets)
    )
    app = FakeApp()
    namespace = {
        "app": app,
        "Request": object,
        "Depends": lambda value: value,
        "get_verified_user": lambda: None,
        "HTTPException": FakeHTTPException,
        "JSONResponse": FakeJSONResponse,
    }
    exec(compile(route, "receipt-route-fixture", "exec"), namespace)
    return app.routes["/api/v1/hades/receipt/apply"]


def run_apply_process(base_url, body, output):
    os.environ["HADES_RECEIPT_GROCY_URL"] = base_url
    route = load_apply_route()
    user = type("SyntheticOwner", (), {"id": "owner-1", "role": "admin"})()
    result = asyncio.run(route(FakeRequest(body), user))
    output.put(result.value)


async def main():
    route = load_apply_route()
    with tempfile.TemporaryDirectory(prefix="hades-receipt-apply-") as directory:
        root = Path(directory)
        ledger = root / "fingerprints.json"
        api_key = root / "grocy.key"
        api_key.write_text("synthetic-grocy-key\n", encoding="utf-8")
        api_key.chmod(0o600)
        os.environ.update({
            "WEBUI_SECRET_KEY": "synthetic-webui-signing-key",
            "HADES_RECEIPT_OWNER_USER_ID": "owner-1",
            "HADES_RECEIPT_LEDGER_PATH": str(ledger),
            "HADES_RECEIPT_GROCY_API_KEY_FILE": str(api_key),
            "HADES_RECEIPT_GROCY_URL": "http://synthetic-grocy",
        })

        fingerprint = hashlib.sha256(b"synthetic receipt bytes").hexdigest()
        preview_items = [{
            "name": "Milk",
            "product_id": 5,
            "candidates": [{"product_id": 5, "name": "Milk"}],
        }]
        canonical = json.dumps(
            {"fingerprint": fingerprint, "items": preview_items},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        token = hmac.new(b"synthetic-webui-signing-key", canonical, hashlib.sha256).hexdigest()
        body = {
            "confirm": True,
            "receipt_fingerprint": fingerprint,
            "review_token": token,
            "preview_items": preview_items,
            "items": [{"name": "Milk", "product_id": 5, "amount": "2"}],
        }

        lock = Lock()
        server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticGrocyHandler)
        server.state_lock = lock
        server.writes = []
        server.stock = 7.0
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        os.environ["HADES_RECEIPT_GROCY_URL"] = base_url

        context = multiprocessing.get_context("fork")
        output = context.Queue()
        workers = [context.Process(target=run_apply_process, args=(base_url, body, output)) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
        assert all(not worker.is_alive() and worker.exitcode == 0 for worker in workers), [
            (worker.pid, worker.exitcode, worker.is_alive()) for worker in workers
        ]
        payloads = [output.get(timeout=3) for _ in workers]
        assert sum(value["status"] == "SUCCEEDED" for value in payloads) == 1, payloads
        assert sum(value["status"] == "ALREADY APPLIED" for value in payloads) == 7, payloads
        assert len(server.writes) == 1, server.writes
        assert server.stock == 9.0, server.stock
        assert ledger.stat().st_mode & 0o777 == 0o600

        route = load_apply_route()
        user = type("SyntheticOwner", (), {"id": "owner-1", "role": "admin"})()
        ledger.chmod(0o644)
        second_fingerprint = hashlib.sha256(b"unsafe-ledger receipt").hexdigest()
        second_preview = [{"name": "Milk", "product_id": 5, "candidates": [{"product_id": 5}]}]
        second_payload = json.dumps(
            {"fingerprint": second_fingerprint, "items": second_preview},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        second_token = hmac.new(b"synthetic-webui-signing-key", second_payload, hashlib.sha256).hexdigest()
        invalid = await route(FakeRequest({
            **body,
            "receipt_fingerprint": second_fingerprint,
            "review_token": second_token,
            "preview_items": second_preview,
        }), user)
        assert invalid.value["status"] == "FAILED", invalid.value
        assert invalid.value["writes_performed"] is False, invalid.value
        assert len(server.writes) == 1, server.writes

        ledger.chmod(0o600)
        full_ledger = {
            hashlib.sha256(f"synthetic-{index}".encode()).hexdigest(): {"status": "APPLIED"}
            for index in range(4096)
        }
        ledger.write_text(json.dumps({"fingerprints": full_ledger}), encoding="utf-8")
        ledger.chmod(0o600)
        third_fingerprint = hashlib.sha256(b"full-ledger receipt").hexdigest()
        third_preview = [{"name": "Milk", "product_id": 5, "candidates": [{"product_id": 5}]}]
        third_payload = json.dumps(
            {"fingerprint": third_fingerprint, "items": third_preview},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        third_token = hmac.new(b"synthetic-webui-signing-key", third_payload, hashlib.sha256).hexdigest()
        full = await route(FakeRequest({
            **body,
            "receipt_fingerprint": third_fingerprint,
            "review_token": third_token,
            "preview_items": third_preview,
        }), user)
        assert full.value["status"] == "FAILED", full.value
        assert full.value["writes_performed"] is False, full.value
        assert len(server.writes) == 1, server.writes
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    print("PASS eight independent worker processes confirming one receipt perform exactly one canonical Grocy write")
    print("PASS unsafe receipt-ledger permissions fail closed before any pantry write")
    print("PASS a full bounded receipt ledger rejects new intake before any pantry write")


if __name__ == "__main__":
    asyncio.run(main())
