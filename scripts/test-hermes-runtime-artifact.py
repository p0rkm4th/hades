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
    (repo / "integrations").mkdir()
    shutil.copyfile(TOOL, repo / "scripts/hermes-runtime-artifact.py")
    source = b"# synthetic Hermes overlay\nVALUE = 'fixture'\n"
    support = b"# synthetic runtime view helper\nVALUE = 'support-fixture'\n"
    (repo / "hermes/sitecustomize.py").write_bytes(source)
    (repo / "integrations/homelab_views.py").write_bytes(support)
    config = root / "hermes-profile.yaml"
    config.write_text("mcp_servers: {}\n", encoding="utf-8")
    run("git", "-C", str(repo), "init", "-q")
    run("git", "-C", str(repo), "config", "user.name", "fixture")
    run("git", "-C", str(repo), "config", "user.email", "fixture@example.invalid")
    run("git", "-C", str(repo), "add", "hermes/sitecustomize.py", "integrations/homelab_views.py", "scripts/hermes-runtime-artifact.py")
    run("git", "-C", str(repo), "commit", "-qm", "fixture source")

    outputs = []
    for name in ("first", "second"):
        output_dir = root / name
        output_dir.mkdir()
        artifact = output_dir / "sitecustomize.py"
        manifest = output_dir / "sitecustomize.runtime.json"
        run(
            os.environ.get("PYTHON", "python3"), str(TOOL), "build",
            "--source-repo", str(repo), "--hermes-version", "0.21.2",
            "--config-input", f"profile={config}",
            "--artifact", str(artifact), "--manifest", str(manifest),
        )
        outputs.append((artifact.read_bytes(), (output_dir / "homelab_views.py").read_bytes(), manifest.read_bytes()))
    assert outputs[0] == outputs[1], "identical inputs must produce byte-identical output and manifest"
    assert (root / "first/sitecustomize.py").stat().st_mode & 0o777 == 0o600
    assert (root / "first/homelab_views.py").stat().st_mode & 0o777 == 0o600
    assert (root / "first/sitecustomize.runtime.json").stat().st_mode & 0o777 == 0o600
    assert outputs[0][0] == source, "runtime artifact must be the exact tracked source copy"
    assert outputs[0][1] == support, "runtime helper must be the exact tracked source copy"
    manifest = json.loads(outputs[0][2])
    assert manifest["schema"] == "hades/hermes-runtime-overlay/v2"
    assert manifest["hades_git_sha"] == git(repo, "rev-parse", "HEAD")
    assert manifest["input_artifact_sha256"]["hermes/sitecustomize.py"] == hashlib.sha256(source).hexdigest()
    assert manifest["generated_artifact"]["sha256"] == hashlib.sha256(source).hexdigest()
    assert manifest["supporting_artifacts"]["integrations/homelab_views.py"]["sha256"] == hashlib.sha256(support).hexdigest()
    assert runtime_tool.support_artifact_sha(manifest) == hashlib.sha256(support).hexdigest()
    assert manifest["configuration_inputs"][0]["name"] == "profile"
    assert manifest["manifest_id"] == hashlib.sha256(
        (json.dumps({k: v for k, v in manifest.items() if k != "manifest_id"}, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    collision = root / "collision"
    collision.mkdir()
    preserved_support = collision / "homelab_views.py"
    preserved_support.write_bytes(b"pre-existing support must survive failed build")
    collision_build = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "build",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(collision / "sitecustomize.py"),
        "--manifest", str(collision / "sitecustomize.runtime.json"), check=False,
    )
    assert collision_build.returncode != 0
    assert preserved_support.read_bytes() == b"pre-existing support must survive failed build"
    assert not (collision / "sitecustomize.py").exists()
    fingerprint = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "fingerprint",
        "--config-input", f"profile={config}",
    ).stdout
    assert f"profile=sha256:{hashlib.sha256(config.read_bytes()).hexdigest()}" in fingerprint
    assert manifest["runtime_configuration_id"] in fingerprint

    sentinel = "SYNTHETIC_SECRET_MUST_NOT_APPEAR_IN_DIAGNOSTICS_7f29c1"
    protected = root / "protected-hermes.env"
    protected.write_text(f"API_SERVER_KEY={sentinel}\nGROCY_API_KEY=synthetic-grocy\n", encoding="utf-8")
    safe_output = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "fingerprint",
        "--config-input", f"hermes-env={protected}",
    )
    assert sentinel not in safe_output.stdout + safe_output.stderr
    assert "API_SERVER_KEY" not in safe_output.stdout + safe_output.stderr
    assert "GROCY_API_KEY" not in safe_output.stdout + safe_output.stderr

    run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first/sitecustomize.py"), "--manifest", str(root / "first/sitecustomize.runtime.json"),
        "--installed", str(root / "first/sitecustomize.py"),
        "--installed-support", str(root / "first/homelab_views.py"),
    )
    wrong_support = root / "wrong-homelab_views.py"
    wrong_support.write_bytes(b"VALUE = 'wrong support module'\n")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first/sitecustomize.py"), "--manifest", str(root / "first/sitecustomize.runtime.json"),
        "--installed-support", str(wrong_support), check=False,
    )
    assert rejected.returncode != 0 and "installed runtime support file differs" in rejected.stderr
    run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify-config",
        "--config-input", f"profile={config}", "--manifest", str(root / "first/sitecustomize.runtime.json"),
    )
    wrong_loaded = root / "wrong-sitecustomize.py"
    wrong_loaded.write_bytes(b"VALUE = 'wrong import path'\n")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first/sitecustomize.py"), "--manifest", str(root / "first/sitecustomize.runtime.json"),
        "--installed", str(wrong_loaded), check=False,
    )
    assert rejected.returncode != 0 and "installed runtime file differs" in rejected.stderr

    config.write_text("mcp_servers: {changed: true}\n", encoding="utf-8")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first/sitecustomize.py"), "--manifest", str(root / "first/sitecustomize.runtime.json"), check=False,
    )
    assert rejected.returncode != 0 and "manifest differs" in rejected.stderr
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify-config",
        "--config-input", f"profile={config}", "--manifest", str(root / "first/sitecustomize.runtime.json"), check=False,
    )
    assert rejected.returncode != 0 and "configuration differs" in rejected.stderr

    (repo / "hermes/sitecustomize.py").write_bytes(b"VALUE = 'drift'\n")
    rejected = run(
        os.environ.get("PYTHON", "python3"), str(TOOL), "verify",
        "--source-repo", str(repo), "--hermes-version", "0.21.2",
        "--config-input", f"profile={config}",
        "--artifact", str(root / "first/sitecustomize.py"), "--manifest", str(root / "first/sitecustomize.runtime.json"), check=False,
    )
    assert rejected.returncode != 0 and "source repository must be clean" in rejected.stderr

print("PASS deterministic Hermes runtime source bundle, manifest, config identity, and wrong-file detection")
