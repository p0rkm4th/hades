#!/usr/bin/env python3
"""Private fixed-source endpoint for the approved Backup Verification graph."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The deployed copy lives under <generated-full>/config/epsilon-source. Add
# that generated root so the shared HADES automation package resolves without
# borrowing the development checkout or relying on an undeclared PYTHONPATH.
_HADES_SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(_HADES_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_HADES_SOURCE_ROOT))

from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority
from integrations.automation.phase3_request import Phase3RequestError, make_phase3_http_handler
from integrations.automation.phase3_self_service import Phase3Catalog, Phase3Runner, Phase3Store

ROOT = Path(os.environ.get("HADES_EPSILON_BACKUP_ROOT", "/var/lib/hades/epsilon-backup-evidence"))
BIND = os.environ.get("HADES_EPSILON_SOURCE_BIND", "127.0.0.1")
PORT = int(os.environ.get("HADES_EPSILON_SOURCE_PORT", "8643"))
HEALTH_URL = os.environ.get("HADES_EPSILON_HEALTH_URL", "").strip()
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
    custody = os.environ.get(
        "HADES_EPSILON_BACKUP_CUSTODY_LABEL",
        "operator-configured protected staging location",
    ).strip()[:120]
    base = {"hades_template": "backup-verification", "target": name, "label": label, "custody": custody, "observed_at": observed}
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
    key_file = os.environ.get("HADES_GROCY_API_KEY_FILE", "/etc/hades/secrets/grocy/api_key")
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
            "schema", "hades_sha", "hades_tree_sha256", "infra_sha", "infra_tree_sha256", "hermes_version", "hermes_runtime_kind", "hermes_executable_sha256", "overlay_sha256",
            "hermes_profile_sha256", "mcp_runtime_sha256", "task_store_sha256", "manifest_sha256", "epsilon_package_manifest_sha256",
            "generated_at", "deployment_path", "classification",
        }
        return {"status": "READY", **{key: value[key] for key in allowed if key in value}}
    except (OSError, ValueError, TypeError):
        return {"status": "UNAVAILABLE", "reason": "provenance artifact could not be read"}


def _phase3_private_bytes(path_value: str, *, minimum: int, maximum: int) -> bytes:
    if not path_value:
        raise RuntimeError("Phase 3 private input is not configured")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path_value, flags)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size < minimum
            or info.st_size > maximum
        ):
            raise Phase3RequestError("Phase 3 private input is unavailable")
        value = os.read(fd, maximum + 1)
    finally:
        os.close(fd)
    if len(value) < minimum or len(value) > maximum:
        raise Phase3RequestError("Phase 3 private input is unavailable")
    return value


def _phase3_health_read(_payload: dict[str, object]) -> dict[str, object]:
    if not HEALTH_URL:
        return {
            "hades_state": "SOURCE_UNAVAILABLE",
            "hades_reason": "canonical HADES health source is not configured",
            "observed_at": time.time(),
        }
    request = urllib.request.Request(HEALTH_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            value = json.loads(response.read())
        if not isinstance(value, dict):
            return {"hades_state": "UNKNOWN", "hades_reason": "health source returned no canonical state"}
        status = value.get("status")
        state = value.get("state")
        if status is True or state == "UP":
            return {"hades_state": "UP", "hades_reason": "canonical HADES health status", "observed_at": time.time()}
        if status is False or state == "DOWN":
            return {"hades_state": "DOWN", "hades_reason": "canonical HADES health status", "observed_at": time.time()}
        return {"hades_state": "UNKNOWN", "hades_reason": "health source returned no canonical state", "observed_at": time.time()}
    except Exception as exc:
        return {"hades_state": "SOURCE_UNAVAILABLE", "hades_reason": f"health source unavailable ({type(exc).__name__})", "observed_at": time.time()}


def _phase3_backup_read(_payload: dict[str, object]) -> dict[str, object]:
    results = [verify("hades"), verify("infra")]
    return {
        "hades_state": "HEALTHY" if all(item["hades_state"] == "HEALTHY" for item in results) else "ATTENTION",
        "targets": results,
        "observed_at": time.time(),
    }


def _phase3_weekly_read(payload: dict[str, object]) -> dict[str, object]:
    readers = {
        "hades-core.health": _phase3_health_read,
        "grocy.household": lambda _payload: inventory(),
        "backup.evidence": _phase3_backup_read,
    }
    scope = payload.get("resource_scope", [])
    if not isinstance(scope, list) or not scope or any(not isinstance(item, str) or item not in readers for item in scope):
        return {"hades_state": "FAILED", "hades_reason": "weekly summary scope is invalid"}
    results = {resource: readers[resource](payload) for resource in sorted(set(scope))}
    state = "READY" if all(
        value.get("hades_state") not in {"SOURCE_UNAVAILABLE", "FAILED", "ATTENTION", "UNKNOWN"}
        for value in results.values()
    ) else "PARTIAL"
    return {"hades_state": state, "sources": results, "observed_at": time.time()}


def _phase3_runner() -> Phase3Runner:
    state_path = os.environ.get("HADES_EPSILON_PHASE3_STATE_FILE", "").strip()
    directory_path = os.environ.get("HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE", "").strip()
    directory_url = os.environ.get("HADES_EPSILON_PHASE3_LLDAP_URL", "").strip()
    directory_password = os.environ.get("HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE", "").strip()
    if not state_path:
        raise RuntimeError("Phase 3 runner state is not configured")
    directory_inputs = (directory_path, directory_url, directory_password)
    if not all(directory_inputs):
        raise RuntimeError("Phase 3 live directory authority inputs are incomplete")
    policy = Phase3LldapAuthority(directory_path, directory_password, directory_url)
    sources = {
        "server-health-watch": _phase3_health_read,
        "low-inventory-summary": lambda _payload: inventory(),
        "weekly-household-summary": _phase3_weekly_read,
        "hades-backup-verification": _phase3_backup_read,
    }
    return Phase3Runner(
        Phase3Store(state_path),
        policy,
        sources,
        catalog=Phase3Catalog({"hades-core": "HADES Core"}),
    )


def _phase3_signing_key() -> bytes:
    return _phase3_private_hmac_key("HADES_EPSILON_PHASE3_HMAC_KEY_FILE")


def _phase3_result_signing_key() -> bytes:
    """Separate HADES-only credential; never expose the n8n run key for reads."""
    return _phase3_private_hmac_key("HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE")


def _phase3_private_hmac_key(environment_name: str) -> bytes:
    path = os.environ.get(environment_name, "").strip()
    key = _phase3_private_bytes(path, minimum=32, maximum=256).rstrip(b"\r\n")
    if len(key) < 32:
        raise Phase3RequestError("Phase 3 private input is unavailable")
    return key


_phase3_result_key_configured = bool(
    os.environ.get("HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE", "").strip()
)
_Phase3HTTPHandler = make_phase3_http_handler(
    _phase3_signing_key,
    _phase3_runner,
    _phase3_result_signing_key if _phase3_result_key_configured else None,
)


class Handler(_Phase3HTTPHandler):
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
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
