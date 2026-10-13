#!/usr/bin/env python3
"""Prove deterministic source-copy composition and fail-closed verification."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/hermes-runtime-artifact.py"
spec = importlib.util.spec_from_file_location("hades_runtime_artifact", TOOL)
runtime_tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(runtime_tool)

try:
    runtime_tool._pid_snapshot("hades-hermes.service")
except runtime_tool.RuntimeUnknown:
    pass
else:
    raise AssertionError("inactive or unobservable service must not be reported as verified")


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def git(repo: Path, *args: str) -> str:
    return run("git", "-C", str(repo), *args).stdout.strip()


with tempfile.TemporaryDirectory(prefix="hades-runtime-artifact-") as temporary:
    root = Path(temporary)
    repo = root / "source"
    (repo / "hermes").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "config").mkdir()
    shutil.copyfile(TOOL, repo / "scripts/hermes-runtime-artifact.py")
    source = b"# synthetic Hermes overlay\nVALUE = 'fixture'\n"
    (repo / "hermes/sitecustomize.py").write_bytes(source)
    config = root / "hermes-profile.yaml"
    config.write_text("mcp_servers: {}\n", encoding="utf-8")
    run("git", "-C", str(repo), "init", "-q")
    run("git", "-C", str(repo), "config", "user.name", "fixture")
    run("git", "-C", str(repo), "config", "user.email", "fixture@example.invalid")
    run("git", "-C", str(repo), "add", "hermes/sitecustomize.py", "scripts/hermes-runtime-artifact.py")
    run("git", "-C", str(repo), "commit", "-qm", "fixture source")

    outputs = []
    for name in ("first", "second"):
        artifact = root / f"{name}.py"
        manifest = root / f"{name}.json"
        run(
            os.environ.get("PYTHON", "python3"), str(TOOL), "build",
            "--source-repo", str(repo), "--hermes-version", "0.21.2",
            "--config-input", f"profile={config}",
            "--artifact", str(artifact), "--manifest", str(manifest),
        )
        outputs.append((artifact.read_bytes(), manifest.read_bytes()))
    assert outputs[0] == outputs[1], "identical inputs must produce byte-identical output and manifest"
    assert (root / "first.py").stat().st_mode & 0o777 == 0o600
    assert (root / "first.json").stat().st_mode & 0o777 == 0o600
    assert outputs[0][0] == source, "runtime artifact must be the exact tracked source copy"
    manifest = json.loads(outputs[0][1])
    assert manifest["schema"] == "hades/hermes-runtime-overlay/v1"
    assert manifest["hades_git_sha"] == git(repo, "rev-parse", "HEAD")
    assert manifest["input_artifact_sha256"]["hermes/sitecustomize.py"] == hashlib.sha256(source).hexdigest()
    assert manifest["generated_artifact"]["sha256"] == hashlib.sha256(source).hexdigest()
    assert manifest["configuration_inputs"][0]["name"] == "profile"
    assert manifest["manifest_id"] == hashlib.sha256(
        (json.dumps({k: v for k, v in manifest.items() if k != "manifest_id"}, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    fingerprint = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "fingerprint",
        "--config-input", f"profile={config}",
    ).stdout
    assert f"profile=sha256:{hashlib.sha256(config.read_bytes()).hexdigest()}" in fingerprint
    assert manifest["runtime_configuration_id"] in fingerprint

    run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first.py"), "--manifest", str(root / "first.json"),
        "--installed", str(root / "first.py"),
    )
    run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify-config",
        "--config-input", f"profile={config}", "--manifest", str(root / "first.json"),
    )
    wrong_loaded = root / "wrong-sitecustomize.py"
    wrong_loaded.write_bytes(b"VALUE = 'wrong import path'\n")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first.py"), "--manifest", str(root / "first.json"),
        "--installed", str(wrong_loaded), check=False,
    )
    assert rejected.returncode != 0 and "installed runtime file differs" in rejected.stderr

    config.write_text("mcp_servers: {changed: true}\n", encoding="utf-8")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first.py"), "--manifest", str(root / "first.json"), check=False,
    )
    assert rejected.returncode != 0 and "manifest differs" in rejected.stderr
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify-config",
        "--config-input", f"profile={config}", "--manifest", str(root / "first.json"), check=False,
    )
    assert rejected.returncode != 0 and "configuration differs" in rejected.stderr

    (repo / "hermes/sitecustomize.py").write_bytes(b"VALUE = 'drift'\n")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first.py"), "--manifest", str(root / "first.json"), check=False,
    )
    assert rejected.returncode != 0 and "source repository must be clean" in rejected.stderr

print("PASS deterministic Hermes runtime artifact, manifest, config identity, and wrong-file detection")
