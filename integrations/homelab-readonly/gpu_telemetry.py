"""Bounded, read-only GPU telemetry over a fixed SSH command contract.

Every endpoint is an operator-owned inference endpoint ID, never a user-supplied
host. The remote account must enforce the documented ForceCommand independently.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


CONFIG_ENV = "HADES_GPU_TELEMETRY_CONFIG_FILE"
REMOTE_COMMAND = "hades-gpu-telemetry-v1"
MAX_CONFIG_BYTES = 16384
MAX_OUTPUT_BYTES = 32768
MAX_ENDPOINTS = 16
MAX_GPUS_PER_ENDPOINT = 32
TIMEOUT_SECONDS = 5
_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
_USER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}\Z")


def _protected_file(value: object, *, modes: set[int], label: str) -> Path:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        raise ValueError(f"GPU telemetry {label} path must be absolute")
    path = Path(value)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"GPU telemetry {label} must be a regular non-symlink file")
    if path.stat().st_mode & 0o777 not in modes:
        raise ValueError(f"GPU telemetry {label} has unsafe permissions")
    return path


def load_specs(config_file: str | None = None) -> tuple[dict[str, object], ...]:
    """Load a private list of approved inference IDs and SSH trust inputs."""
    config_file = (config_file if config_file is not None else os.environ.get(CONFIG_ENV, "")).strip()
    if not config_file:
        return ()
    config = _protected_file(config_file, modes={0o600}, label="configuration")
    if config.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError("GPU telemetry configuration exceeds the bounded size")
    document = json.loads(config.read_text(encoding="utf-8"))
    entries = document.get("endpoints") if isinstance(document, dict) else None
    if not isinstance(entries, list) or not entries or len(entries) > MAX_ENDPOINTS:
        raise ValueError("GPU telemetry configuration must contain 1 to 16 endpoints")
    result = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "inference_id", "host", "user", "identity_file", "known_hosts_file"
        }:
            raise ValueError("GPU telemetry endpoint has missing or unsupported fields")
        inference_id, host, user = entry["inference_id"], entry["host"], entry["user"]
        if not isinstance(inference_id, str) or not _ID.fullmatch(inference_id) or inference_id in seen:
            raise ValueError("GPU telemetry inference IDs must be valid and unique")
        if not isinstance(host, str) or not _HOST.fullmatch(host):
            raise ValueError("GPU telemetry host must be a hostname or address without SSH syntax")
        if not isinstance(user, str) or not _USER.fullmatch(user):
            raise ValueError("GPU telemetry user is invalid")
        seen.add(inference_id)
        key = _protected_file(entry["identity_file"], modes={0o600}, label="identity key")
        known_hosts = _protected_file(
            entry["known_hosts_file"], modes={0o600, 0o644}, label="known-hosts file"
        )
        result.append({
            "inference_id": inference_id,
            "host": host,
            "user": user,
            "identity_file": str(key),
            "known_hosts_file": str(known_hosts),
        })
    return tuple(result)


def _parse_output(output: bytes) -> list[dict[str, object]]:
    if not output or len(output) > MAX_OUTPUT_BYTES:
        raise ValueError("empty or oversized GPU telemetry response")
    text = output.decode("utf-8", errors="strict")
    rows = list(csv.reader(io.StringIO(text), strict=True))
    if not rows or len(rows) > MAX_GPUS_PER_ENDPOINT:
        raise ValueError("GPU telemetry response has an invalid row count")
    result = []
    seen_indices: set[int] = set()
    for row in rows:
        if len(row) != 7:
            raise ValueError("GPU telemetry row has an invalid field count")
        index, uuid, name, total, free, gpu_util, memory_util = (part.strip() for part in row)
        if not index.isdigit() or not uuid.startswith("GPU-") or not name:
            raise ValueError("GPU telemetry identity fields are invalid")
        if len(index) > 3 or len(uuid) > 96 or len(name) > 128:
            raise ValueError("GPU telemetry identity fields exceed their bounds")
        if not all(char.isprintable() for char in uuid + name):
            raise ValueError("GPU telemetry identity fields contain control characters")
        parsed_index = int(index)
        if parsed_index in seen_indices:
            raise ValueError("GPU telemetry contains duplicate device indices")
        seen_indices.add(parsed_index)

        def number(value: str, field: str) -> int | None:
            if value in {"N/A", "Not Supported", "[N/A]"}:
                return None
            if not value.isdigit():
                raise ValueError(f"GPU telemetry {field} is invalid")
            return int(value)

        total_mib, free_mib = number(total, "total memory"), number(free, "free memory")
        gpu_percent, memory_percent = number(gpu_util, "GPU utilization"), number(memory_util, "memory utilization")
        if (total_mib is not None and total_mib <= 0) or (
            free_mib is not None and total_mib is not None and free_mib > total_mib
        ) or any(value is not None and value > 100 for value in (gpu_percent, memory_percent)):
            raise ValueError("GPU telemetry values are outside valid bounds")
        result.append({
            "index": parsed_index, "uuid": uuid, "name": name,
            "memory_total_mib": total_mib, "memory_free_mib": free_mib,
            "gpu_utilization_percent": gpu_percent,
            "memory_utilization_percent": memory_percent,
        })
    if len({row["uuid"] for row in result}) != len(result):
        raise ValueError("GPU telemetry contains duplicate device identities")
    return result


def _read_one(spec: dict[str, object], *, runner=subprocess.run) -> dict[str, object]:
    started = time.monotonic()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    ssh = shutil.which("ssh")
    if not ssh:
        return {"inference_id": spec["inference_id"], "status": "UNAVAILABLE", "error_code": "SSH_CLIENT_MISSING", "retrieved_at": retrieved_at}
    command = [
        ssh, "-F", "/dev/null", "-T", "-i", str(spec["identity_file"]),
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={spec['known_hosts_file']}",
        "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes",
        "-o", "ForwardAgent=no", "-o", "RequestTTY=no", "-o", "ProxyCommand=none",
        "-o", "ProxyJump=none", "-o", "PermitLocalCommand=no", "-o", "ControlMaster=no",
        "-o", "ConnectTimeout=5",
        "-o", "ServerAliveInterval=2", "-o", "ServerAliveCountMax=1",
        "-l", str(spec["user"]), str(spec["host"]), REMOTE_COMMAND,
    ]
    try:
        completed = runner(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS, check=False, close_fds=True,
        )
        output = completed.stdout or b""
        if len(output) > MAX_OUTPUT_BYTES:
            raise ValueError("oversized GPU telemetry response")
        if completed.returncode != 0:
            if completed.returncode == 124:
                error = "REMOTE_QUERY_TIMEOUT"
            elif completed.returncode == 255:
                error = "SSH_UNAVAILABLE_OR_AUTH_FAILED"
            else:
                error = "REMOTE_COMMAND_FAILED"
            return {"inference_id": spec["inference_id"], "status": "UNAVAILABLE", "error_code": error, "retrieved_at": retrieved_at, "duration_ms": round((time.monotonic() - started) * 1000, 1)}
        devices = _parse_output(output)
        return {"inference_id": spec["inference_id"], "status": "READABLE", "devices": devices, "retrieved_at": retrieved_at, "duration_ms": round((time.monotonic() - started) * 1000, 1)}
    except subprocess.TimeoutExpired:
        error_code = "TIMEOUT"
    except (OSError, UnicodeError, ValueError, csv.Error, json.JSONDecodeError):
        error_code = "INVALID_OR_UNAVAILABLE_RESPONSE"
    return {"inference_id": spec["inference_id"], "status": "UNAVAILABLE", "error_code": error_code, "retrieved_at": retrieved_at, "duration_ms": round((time.monotonic() - started) * 1000, 1)}


def read_gpu_telemetry(config_file: str | None = None, *, runner=subprocess.run) -> dict[str, object]:
    """Return bounded live telemetry; never accepts a host or command from callers."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    try:
        specs = load_specs(config_file)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"status": "CONFIGURATION_ERROR", "source": "restricted SSH GPU telemetry", "retrieved_at": retrieved_at, "endpoints": [], "read_only": True}
    if not specs:
        return {"status": "NOT_CONFIGURED", "source": "restricted SSH GPU telemetry", "retrieved_at": retrieved_at, "endpoints": [], "read_only": True}
    with ThreadPoolExecutor(max_workers=min(4, len(specs))) as pool:
        endpoints = list(pool.map(lambda spec: _read_one(spec, runner=runner), specs))
    readable = sum(endpoint["status"] == "READABLE" for endpoint in endpoints)
    status = "READABLE" if readable == len(endpoints) else "PARTIAL" if readable else "UNAVAILABLE"
    return {"status": status, "source": "restricted SSH GPU telemetry", "retrieved_at": retrieved_at, "endpoints": endpoints, "read_only": True}
