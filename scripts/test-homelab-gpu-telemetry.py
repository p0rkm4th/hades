#!/usr/bin/env python3
"""Synthetic contracts for the fixed-command GPU telemetry reader."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "integrations/homelab-readonly/gpu_telemetry.py"
spec = importlib.util.spec_from_file_location("hades_gpu_telemetry_contract", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    key = root / "synthetic_key"
    known_hosts = root / "known_hosts"
    profile = root / "profile.json"
    key.write_text("synthetic private key material\n", encoding="utf-8")
    key.chmod(0o600)
    known_hosts.write_text("gpu.example.test ssh-ed25519 AAAATEST\n", encoding="utf-8")
    known_hosts.chmod(0o600)
    document = {"endpoints": [{
        "inference_id": "gpu-lane-a", "host": "gpu.example.test", "user": "hades-gpu-ro",
        "identity_file": str(key), "known_hosts_file": str(known_hosts),
    }]}
    profile.write_text(json.dumps(document), encoding="utf-8")
    profile.chmod(0o600)
    specs = module.load_specs(str(profile))
    assert len(specs) == 1 and specs[0]["inference_id"] == "gpu-lane-a"

    sample = b'0, GPU-test-0, Synthetic GPU, 16384, 12000, 10, 22\n'
    seen = []

    def runner(command, **kwargs):
        seen.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=sample)

    result = module.read_gpu_telemetry(str(profile), runner=runner)
    assert result["status"] == "READABLE" and result["read_only"] is True
    endpoint = result["endpoints"][0]
    assert endpoint["status"] == "READABLE"
    assert endpoint["devices"][0]["memory_free_mib"] == 12000
    command, kwargs = seen[0]
    assert command[-1] == module.REMOTE_COMMAND
    assert "StrictHostKeyChecking=yes" in command
    assert "GlobalKnownHostsFile=/dev/null" in command
    assert "-i" in command and str(key) in command
    assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] == module.TIMEOUT_SECONDS
    assert kwargs["stderr"] == subprocess.DEVNULL and kwargs["check"] is False
    assert "arbitrary" not in " ".join(command)

    partial_document = {"endpoints": [
        document["endpoints"][0],
        {**document["endpoints"][0], "inference_id": "gpu-lane-b", "host": "gpu-b.example.test"},
    ]}
    profile.write_text(json.dumps(partial_document), encoding="utf-8")
    profile.chmod(0o600)

    def partial_runner(command, **kwargs):
        if command[-2] == "gpu-b.example.test":
            return SimpleNamespace(returncode=255, stdout=b"")
        return SimpleNamespace(returncode=0, stdout=sample)

    partial = module.read_gpu_telemetry(str(profile), runner=partial_runner)
    assert partial["status"] == "PARTIAL"
    assert [item["status"] for item in partial["endpoints"]] == ["READABLE", "UNAVAILABLE"]

    def fail_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    timed_out = module.read_gpu_telemetry(str(profile), runner=fail_runner)
    assert timed_out["status"] == "UNAVAILABLE"
    assert timed_out["endpoints"][0]["error_code"] == "TIMEOUT"
    profile.unlink()
    assert module.read_gpu_telemetry(str(profile))["status"] == "CONFIGURATION_ERROR"

    profile.write_text(json.dumps(document), encoding="utf-8")
    profile.chmod(0o644)
    assert module.read_gpu_telemetry(str(profile))["status"] == "CONFIGURATION_ERROR"

    profile.chmod(0o600)
    unsafe = json.loads(profile.read_text(encoding="utf-8"))
    unsafe["endpoints"][0]["host"] = "gpu.example.test;touch /tmp/nope"
    profile.write_text(json.dumps(unsafe), encoding="utf-8")
    profile.chmod(0o600)
    try:
        module.load_specs(str(profile))
    except ValueError:
        pass
    else:
        raise AssertionError("SSH syntax was accepted in the configured host")

    for bad in (
        b'0, GPU-test-0, Synthetic GPU, 16384, 17000, 10, 22\n',
        b'0, GPU-test-0, Synthetic GPU, 16384, 12000, 101, 22\n',
        b'0, GPU-test-0, Synthetic GPU, 16384, 12000, 10\n',
    ):
        try:
            module._parse_output(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid GPU telemetry was accepted")

assert module.read_gpu_telemetry(config_file="")["status"] == "NOT_CONFIGURED"
remote_wrapper = (ROOT / "deploy/homelab/gpu-telemetry-command.sh").read_text(encoding="utf-8")
for marker in (
    'SSH_ORIGINAL_COMMAND-',
    '!= "hades-gpu-telemetry-v1"',
    "/usr/bin/timeout 5s /usr/bin/nvidia-smi",
    "--query-gpu=index,uuid,name,memory.total,memory.free,utilization.gpu,utilization.memory",
    "--format=csv,noheader,nounits",
):
    assert marker in remote_wrapper, marker
for forbidden in ("eval ", "sudo ", "/bin/sh -c", "SSH_ORIGINAL_COMMAND)"):
    assert forbidden not in remote_wrapper, forbidden
print("PASS fixed-command GPU telemetry is bounded, read-only, and strict-host-key verified")
