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
project_path = lock_dir / "pyproject.toml"
lock_path = lock_dir / "uv.lock"

for path, key in (
    (project_path, "HADES_HERMES_CANDIDATE_HINDSIGHT_PYPROJECT_SHA256"),
    (lock_path, "HADES_HERMES_CANDIDATE_HINDSIGHT_LOCK_SHA256"),
):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != values[key]:
        raise SystemExit(f"FAIL {path.relative_to(ROOT)} digest differs from {key}")

project = tomllib.loads(project_path.read_text())
lock = tomllib.loads(lock_path.read_text())
if project.get("project", {}).get("version") != values["HADES_HERMES_CANDIDATE_PLUGIN_VERSION"]:
    raise SystemExit("FAIL candidate plugin project version differs from manifest")
if project.get("tool", {}).get("uv", {}).get("package") is not False:
    raise SystemExit("FAIL candidate plugin project must remain a non-package plugin")
packages = {item["name"]: item for item in lock.get("package", [])}
for name, key in (
    ("hindsight-client", "HADES_HERMES_CANDIDATE_HINDSIGHT_CLIENT_VERSION"),
    ("hindsight-embed", "HADES_HERMES_CANDIDATE_HINDSIGHT_EMBED_VERSION"),
):
    item = packages.get(name)
    if not item or item.get("version") != values[key]:
        raise SystemExit(f"FAIL {name} lock version differs from manifest")

registry_packages = [item for item in packages.values() if item.get("source", {}).get("registry")]
if not registry_packages:
    raise SystemExit("FAIL candidate lock contains no registry packages")
for item in registry_packages:
    artifacts = [item.get("sdist", {}), *item.get("wheels", [])]
    hashes = [artifact.get("hash", "") for artifact in artifacts if artifact]
    if not hashes or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in hashes):
        raise SystemExit(f"FAIL {item['name']} lacks immutable SHA-256 artifact hashes")

print(
    "PASS Hermes Hindsight candidate lock: "
    f"{values['HADES_HERMES_CANDIDATE_HINDSIGHT_CLIENT_VERSION']} client, "
    f"{values['HADES_HERMES_CANDIDATE_HINDSIGHT_EMBED_VERSION']} embed, "
    f"{len(registry_packages)} hashed registry packages"
)
