#!/usr/bin/env python3
"""Build and verify a path-free identity manifest for a composed Hermes overlay."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "hades/hermes-overlay-composition/v1"
SOURCE_RELATIVE = "hermes/sitecustomize.py"
FUNCTIONS = (
    "_hades_homelab_guest_visibility_response",
    "_hades_household_homelab_boundary_response",
)
FIELDS = {
    "schema",
    "source_revision",
    "source_tree",
    "base_overlay_sha256",
    "wrapper_sha256",
    "final_overlay_sha256",
}
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("source repository identity is unavailable") from None
    return result.stdout.strip()


def _tracked_source(repo: Path) -> tuple[str, str, bytes]:
    revision = _git(repo, "rev-parse", "--verify", "HEAD")
    tree = _git(repo, "rev-parse", "--verify", "HEAD^{tree}")
    if not _GIT_SHA.fullmatch(revision) or not _GIT_SHA.fullmatch(tree):
        raise ValueError("source repository identity is malformed")
    try:
        source = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{SOURCE_RELATIVE}"],
            check=True,
            capture_output=True,
        ).stdout
        working = (repo / SOURCE_RELATIVE).read_bytes()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("tracked Hermes overlay source is unavailable") from None
    if working != source:
        raise ValueError("Hermes overlay source differs from the recorded Git revision")
    return revision, tree, source


def _composer_module():
    path = Path(__file__).resolve().with_name("prepare-homelab-overlay-candidate.py")
    spec = importlib.util.spec_from_file_location("_hades_overlay_composer", path)
    if spec is None or spec.loader is None:
        raise ValueError("overlay composer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wrapper_hashes(source: bytes) -> dict[str, str]:
    composer = _composer_module()
    spans = composer.source_spans(source, SOURCE_RELATIVE, FUNCTIONS, True)
    return {name: _sha256(source[start:end]) for name, (start, end) in spans.items()}


def build_manifest(repo: Path, base_overlay: bytes, final_overlay: bytes) -> dict[str, Any]:
    """Return a manifest only when final bytes are exactly the tracked composition."""
    repo = Path(repo).resolve(strict=True)
    revision, tree, source = _tracked_source(repo)
    composer = _composer_module()
    expected = composer.compose(base_overlay, source, "base overlay", SOURCE_RELATIVE)
    if expected != final_overlay:
        raise ValueError("final overlay is not the exact tracked-wrapper composition")
    return {
        "schema": SCHEMA,
        "source_revision": revision,
        "source_tree": tree,
        "base_overlay_sha256": _sha256(base_overlay),
        "wrapper_sha256": _wrapper_hashes(source),
        "final_overlay_sha256": _sha256(final_overlay),
    }


def verify_manifest(
    manifest: Any,
    repo: Path,
    final_overlay: bytes,
    base_overlay: bytes | None = None,
) -> bool:
    """Verify exact schema/source/artifact identity and, when given, composition ancestry."""
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise ValueError("composition manifest fields do not match the required schema")
    if manifest.get("schema") != SCHEMA:
        raise ValueError("composition manifest schema is unsupported")
    for field in ("source_revision", "source_tree"):
        if not isinstance(manifest.get(field), str) or not _GIT_SHA.fullmatch(manifest[field]):
            raise ValueError("composition manifest Git identity is malformed")
    for field in ("base_overlay_sha256", "final_overlay_sha256"):
        if not isinstance(manifest.get(field), str) or not _SHA256.fullmatch(manifest[field]):
            raise ValueError("composition manifest digest is malformed")
    hashes = manifest.get("wrapper_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(FUNCTIONS) or any(
        not isinstance(value, str) or not _SHA256.fullmatch(value)
        for value in hashes.values()
    ):
        raise ValueError("composition manifest wrapper digests are malformed")

    revision, tree, source = _tracked_source(Path(repo).resolve(strict=True))
    if manifest["source_revision"] != revision or manifest["source_tree"] != tree:
        raise ValueError("composition manifest source revision/tree is stale")
    if manifest["wrapper_sha256"] != _wrapper_hashes(source):
        raise ValueError("composition manifest wrapper digests are stale")
    if _sha256(final_overlay) != manifest["final_overlay_sha256"]:
        raise ValueError("composed overlay bytes differ from the manifest")
    if base_overlay is not None:
        if _sha256(base_overlay) != manifest["base_overlay_sha256"]:
            # Revalidating an already-installed candidate is explicitly idempotent.
            if _sha256(base_overlay) != manifest["final_overlay_sha256"]:
                raise ValueError("base overlay digest differs from the manifest")
        composer = _composer_module()
        recomposed = composer.compose(base_overlay, source, "base overlay", SOURCE_RELATIVE)
        if recomposed != final_overlay:
            raise ValueError("base overlay does not compose to the recorded final bytes")
    return True
