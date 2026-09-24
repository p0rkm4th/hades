#!/usr/bin/env python3
"""Private fixed-source endpoint for the approved Backup Verification graph."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("HADES_EPSILON_BACKUP_ROOT", "/var/lib/hades/epsilon-backup-evidence"))
BIND = os.environ.get("HADES_EPSILON_SOURCE_BIND", "127.0.0.1")
VERIFY_REPO = Path(os.environ.get("HADES_EPSILON_VERIFY_REPO", "/var/lib/hades/epsilon-backup-verify.git"))
PROVENANCE_FILE = Path(os.environ.get("HADES_DEPLOYED_PROVENANCE_FILE", "/var/lib/hades/epsilon-source/hades-live-provenance.json"))
TARGETS = {
    "hades": ("hades-latest.bundle", "e5a0f0ea7c6668d3dcbe07004d23e3b82ffeee4136f3ac2712efa550ff7ba5e3", "HADES repository backup"),
    "infra": ("hades-infra-latest.bundle", "dc897e3bc44ed853fce73097d18be50f38e3cdf375d299c959353e8b17ba9048", "Infrastructure repository backup"),
}
MAX_AGE = int(os.environ.get("HADES_EPSILON_BACKUP_MAX_AGE", "604800"))


def verify(name: str) -> dict[str, object]:
    filename, expected, label = TARGETS[name]
    observed = time.time()
    path = ROOT / filename
    base = {"hades_template": "backup-verification", "target": name, "label": label, "custody": "Alexandra temporary protected landing zone; verification copy on HADES Core", "observed_at": observed}
    try:
        stat = path.stat()
        if not path.is_file() or stat.st_size <= 0:
            return {**base, "hades_state": "FAILED", "hades_reason": "artifact is empty or not a regular file"}
        age = max(0.0, observed - stat.st_mtime)
        base.update({"artifact_mtime": stat.st_mtime, "age_seconds": age, "freshness": "STALE" if age > MAX_AGE else "CURRENT"})
        if age > MAX_AGE:
            return {**base, "hades_state": "STALE", "hades_reason": "artifact exceeded the configured staleness threshold"}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        base["checksum_matched"] = digest == expected
        if digest != expected:
            return {**base, "hades_state": "FAILED", "hades_reason": "SHA-256 checksum mismatch"}
        result = subprocess.run(["git", "bundle", "verify", str(path)], cwd=VERIFY_REPO, capture_output=True, text=True, timeout=10)
        if result.returncode:
            return {**base, "hades_state": "FAILED", "hades_reason": "git bundle verification failed"}
        return {**base, "hades_state": "HEALTHY", "hades_reason": "checksum matched and git bundle verified", "git_bundle_verified": True}
    except FileNotFoundError:
        return {**base, "hades_state": "MISSING", "hades_reason": "expected backup artifact is missing"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {**base, "hades_state": "SOURCE_UNAVAILABLE", "hades_reason": f"backup custody could not be read: {type(exc).__name__}"}


def inventory() -> dict[str, object]:
    base = {"hades_template": "low-inventory-summary", "source": "Grocy", "observed_at": time.time()}
    key_file = os.environ.get("HADES_GROCY_API_KEY_FILE", "/var/lib/hades/secrets/grocy-api-key")
    try:
        key = Path(key_file).read_text().strip()
        request = urllib.request.Request("http://127.0.0.1:7003/api/stock", headers={"GROCY-API-KEY": key, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            rows = json.loads(response.read())
        low, out, no_minimum = [], [], []
        for row in rows:
            product = row.get("product") or {}
            name = str(product.get("name") or row.get("product_id") or "").strip()
            amount = row.get("amount_aggregated", row.get("amount"))
            minimum = row.get("amount_aggregated_min_stock", row.get("min_stock_amount", product.get("min_stock_amount")))
            if not name or amount is None: continue
            if float(amount) <= 0: out.append(name)
            elif minimum is None: no_minimum.append(name)
            elif float(amount) < float(minimum): low.append(name)
        return {**base, "hades_state": "READY", "hades_reason": "current Grocy stock read", "low": low, "out": out, "no_minimum": no_minimum, "freshness": "CURRENT"}
    except Exception as exc:
        return {**base, "hades_state": "SOURCE_UNAVAILABLE", "hades_reason": f"Grocy source unavailable: {type(exc).__name__}"}


def provenance() -> dict[str, object]:
    """Return only the bounded, non-secret deployment identity artifact."""
    try:
        if not PROVENANCE_FILE.is_file() or PROVENANCE_FILE.is_symlink():
            return {"status": "UNAVAILABLE", "reason": "provenance artifact is missing"}
        value = json.loads(PROVENANCE_FILE.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {"status": "UNAVAILABLE", "reason": "provenance artifact is not an object"}
        allowed = {
            "schema", "hades_sha", "infra_sha", "hermes_version", "overlay_sha256",
            "manifest_sha256", "generated_at", "deployment_path", "classification",
        }
        return {"status": "READY", **{key: value[key] for key in allowed if key in value}}
    except (OSError, ValueError, TypeError):
        return {"status": "UNAVAILABLE", "reason": "provenance artifact could not be read"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        routes = {"/v1/epsilon/backup/hades": "hades", "/v1/epsilon/backup/infra": "infra"}
        if self.path == "/v1/epsilon/inventory":
            body = json.dumps(inventory(), separators=(",", ":")).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path == "/v1/epsilon/provenance":
            body = json.dumps(provenance(), separators=(",", ":")).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        target = routes.get(self.path)
        if not target:
            self.send_error(404)
            return
        body = json.dumps(verify(target), separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, 8643), Handler).serve_forever()
