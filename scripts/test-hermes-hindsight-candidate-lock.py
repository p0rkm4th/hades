#!/usr/bin/env python3
"""Validate immutable candidate inputs for the Hermes Hindsight plugin."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def manifest_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (ROOT / "config/versions.env").read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


values = manifest_values()
lock_dir = ROOT / values["HADES_HERMES_CANDIDATE_HINDSIGHT_LOCK_PATH"]
workspace_path = lock_dir / "pyproject.toml"
project_path = lock_dir / "plugin" / "pyproject.toml"
source_project_path = lock_dir / "hindsight-source-pyproject.toml"
lock_path = lock_dir / "uv.lock"

for path, key in (
    (workspace_path, "HADES_HERMES_CANDIDATE_HERMES_WORKSPACE_PYPROJECT_SHA256"),
    (project_path, "HADES_HERMES_CANDIDATE_HINDSIGHT_PYPROJECT_SHA256"),
    (source_project_path, "HADES_HERMES_CANDIDATE_HINDSIGHT_SOURCE_PYPROJECT_SHA256"),
    (lock_path, "HADES_HERMES_CANDIDATE_HINDSIGHT_LOCK_SHA256"),
):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != values[key]:
        raise SystemExit(f"FAIL {path.relative_to(ROOT)} digest differs from {key}")

workspace = tomllib.loads(workspace_path.read_text())
project = tomllib.loads(project_path.read_text())
source_project = tomllib.loads(source_project_path.read_text())
lock = tomllib.loads(lock_path.read_text())
if project.get("project", {}).get("version") != values["HADES_HERMES_CANDIDATE_PLUGIN_VERSION"]:
    raise SystemExit("FAIL candidate plugin project version differs from manifest")
if project.get("tool", {}).get("uv", {}).get("package") is not False:
    raise SystemExit("FAIL candidate plugin project must remain a non-package plugin")
if source_project.get("project", {}).get("version") != project["project"]["version"]:
    raise SystemExit("FAIL candidate plugin version differs from its official source manifest")
members = workspace.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
if "plugin" not in members:
    raise SystemExit("FAIL candidate Hermes workspace does not include the Hindsight plugin")
if "sys_platform == 'linux'" not in " ".join(workspace.get("tool", {}).get("uv", {}).get("environments", [])):
    raise SystemExit("FAIL candidate lock is not explicitly scoped to the HADES Linux runtime")
for name, key in (
    ("hindsight-client", "HADES_HERMES_CANDIDATE_HINDSIGHT_CLIENT_VERSION"),
    ("hindsight-embed", "HADES_HERMES_CANDIDATE_HINDSIGHT_EMBED_VERSION"),
):
    if f"{name}=={values[key]}" not in project.get("project", {}).get("dependencies", []):
        raise SystemExit(f"FAIL candidate plugin does not exactly pin {name}")
packages = {item["name"]: item for item in lock.get("package", [])}
for name, key in (
    ("hindsight-client", "HADES_HERMES_CANDIDATE_HINDSIGHT_CLIENT_VERSION"),
    ("hindsight-embed", "HADES_HERMES_CANDIDATE_HINDSIGHT_EMBED_VERSION"),
):
    item = packages.get(name)
    if not item or item.get("version") != values[key]:
        raise SystemExit(f"FAIL {name} lock version differs from manifest")

# These core pins are exact in Hermes 0.21.6. The candidate workspace must add
# Hindsight without silently changing the inference/runtime dependency baseline.
for name, expected in {
    "aiohttp": "3.14.3",
    "pydantic": "2.13.4",
    "pydantic-core": "2.46.4",
    "rich": "14.3.3",
    "urllib3": "2.7.0",
}.items():
    if packages.get(name, {}).get("version") != expected:
        raise SystemExit(f"FAIL candidate workspace moved Hermes core pin {name}")

registry_packages = [item for item in packages.values() if item.get("source", {}).get("registry")]
if not registry_packages:
    raise SystemExit("FAIL candidate lock contains no registry packages")
for item in registry_packages:
    artifacts = [item.get("sdist", {}), *item.get("wheels", [])]
    hashes = [artifact.get("hash", "") for artifact in artifacts if artifact]
    if not hashes and item["name"] == "pywin32" and any(
        dependency.startswith("pywin32") and "sys_platform == 'win32'" in dependency
        for dependency in workspace.get("project", {}).get("dependencies", [])
    ):
        # This wheel-only distribution is guarded by Hermes' Windows marker;
        # it has no artifact compatible with this Linux candidate environment.
        continue
    if not hashes or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in hashes):
        raise SystemExit(f"FAIL {item['name']} lacks immutable SHA-256 artifact hashes")

git_packages = [item for item in packages.values() if item.get("source", {}).get("git")]
for item in git_packages:
    revision = re.search(r"(?:[?#]rev=|#)([0-9a-f]{40})(?:$|&)", item["source"].get("git", ""))
    if not revision:
        raise SystemExit(f"FAIL {item['name']} lacks an immutable Git revision")

print(
    "PASS Hermes Hindsight candidate lock: "
    f"{values['HADES_HERMES_CANDIDATE_HINDSIGHT_CLIENT_VERSION']} client, "
    f"{values['HADES_HERMES_CANDIDATE_HINDSIGHT_EMBED_VERSION']} embed, "
    f"{sum(bool(item.get('sdist') or item.get('wheels')) for item in registry_packages)} registry packages with artifact hashes, "
    f"{len(git_packages)} immutable Git packages"
)
