#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root = Path.cwd()
names = ["Spaghetti", "Tomato Sauce", "Ground Beef", "Onion", "Garlic"]
state = {
    "products": [{"id": i + 1, "name": name} for i, name in enumerate(names)],
    "recipes": [],
    "positions": [],
    "shopping": [],
}
state_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        with state_lock:
            if path == "/api/objects/products":
                value = state["products"]
            elif path == "/api/objects/quantity_units":
                value = [{"id": 2, "name": "Piece"}]
            elif path == "/api/objects/recipes":
                value = state["recipes"]
            elif path == "/api/objects/recipes_pos":
                value = state["positions"]
            elif path == "/api/stock":
                value = []
            elif path == "/api/objects/shopping_list":
                value = state["shopping"]
            else:
                self.send_error(404)
                return
            body = json.dumps(value).encode()
        # Widen the read/write race if the canonical action is not locked.
        time.sleep(0.03)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        value = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        with state_lock:
            if path == "/api/objects/recipes":
                created_id = len(state["recipes"]) + 1
                state["recipes"].append({"id": created_id, "name": value["name"]})
            elif path == "/api/objects/recipes_pos":
                state["positions"].append({**value, "id": len(state["positions"]) + 1})
                created_id = len(state["positions"])
            elif path == "/api/objects/shopping_list":
                created_id = len(state["shopping"]) + 1
                state["shopping"].append({"id": created_id, "product_id": value["product_id"], "done": False})
            else:
                self.send_error(404)
                return
            body = json.dumps({"created_object_id": created_id}).encode()
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
    with tempfile.TemporaryDirectory(prefix="hades-grocy-spaghetti-race-") as raw_tmp:
        tmp = Path(raw_tmp)
        env = os.environ.copy()
        env.update({
            "GROCY_URL": f"http://127.0.0.1:{server.server_port}",
            "GROCY_API_KEY": "synthetic-only",
            "HADES_GROCY_AUDIT_FILE": str(tmp / "runtime" / "audit.jsonl"),
            "HADES_OWNER_SUBJECT_IDS": "synthetic-owner",
        })
        code = (
            "import importlib.util; "
            "s=importlib.util.spec_from_file_location('hades_overlay','hermes/sitecustomize.py'); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "print(m._hades_direct_spaghetti_authorized("
            "'Help me make spaghetti tonight and add what is missing', 'synthetic-owner'))"
        )
        commands = [
            subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(2)
        ]
        outputs = [process.communicate(timeout=30) for process in commands]
        assert all(process.returncode == 0 for process in commands), outputs
        with state_lock:
            recipes = list(state["recipes"])
            positions = list(state["positions"])
            shopping = list(state["shopping"])
        assert len(recipes) == 1 and recipes[0]["name"] == "HADES Owner Spaghetti Draft", recipes
        assert len(positions) == 5, positions
        counts = {product_id: sum(row["product_id"] == product_id and not row["done"] for row in shopping) for product_id in range(1, 6)}
        assert counts == {product_id: 1 for product_id in range(1, 6)}, counts
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)

print("PASS concurrent owner spaghetti action: one canonical recipe, five ingredients, one shopping row per missing product")
PY
