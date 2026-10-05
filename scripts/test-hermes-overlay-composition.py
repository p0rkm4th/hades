#!/usr/bin/env python3
"""Synthetic contracts for Hermes composed-overlay manifests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/hermes-overlay-composition.py"
COMPOSER_PATH = ROOT / "scripts/prepare-homelab-overlay-candidate.py"
spec = importlib.util.spec_from_file_location("overlay_manifest", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def must_fail(call, phrase: str) -> None:
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected ValueError containing {phrase!r}")


with tempfile.TemporaryDirectory(prefix="hades-overlay-manifest-") as directory:
    repo = Path(directory)
    (repo / "hermes").mkdir()
    (repo / "scripts").mkdir()
    (repo / "scripts/prepare-homelab-overlay-candidate.py").write_bytes(COMPOSER_PATH.read_bytes())
    source = b'''def _hades_load_homelab_views():\n    return view_loader()\n\ndef _hades_homelab_guest_visibility_response(summary):\n    return _hades_load_homelab_views().guest(summary)\n\ndef _hades_household_homelab_boundary_response(user_text):\n    return _hades_load_homelab_views().household(user_text)\n'''
    (repo / "hermes/sitecustomize.py").write_bytes(source)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "synthetic@example.invalid")
    git(repo, "config", "user.name", "Synthetic Test")
    git(repo, "add", "hermes/sitecustomize.py", "scripts/prepare-homelab-overlay-candidate.py")
    git(repo, "commit", "-qm", "synthetic source")

    base = b'''# deployment-local helper retained\nLOCAL_FLAG = True\ndef _hades_load_homelab_views():\n    return view_loader()\ndef _hades_homelab_guest_visibility_response(summary):\n    return old_guest(summary)\ndef _hades_household_homelab_boundary_response(user_text):\n    return old_household(user_text)\n'''
    composer_spec = importlib.util.spec_from_file_location("test_composer", repo / "scripts/prepare-homelab-overlay-candidate.py")
    assert composer_spec and composer_spec.loader
    composer = importlib.util.module_from_spec(composer_spec)
    composer_spec.loader.exec_module(composer)
    final = composer.compose(base, source, "base.py", "tracked.py")
    manifest = module.build_manifest(repo, base, final)
    assert module.verify_manifest(manifest, repo, final, base)
    assert module.verify_manifest(manifest, repo, final, final)  # installed revalidation
    assert "LOCAL_FLAG = True" in final.decode()
    encoded = json.dumps(manifest, sort_keys=True)
    assert "/tmp/" not in encoded and "sitecustomize.py" not in encoded
    print("PASS build, verify, and idempotent installed-overlay verification")

    must_fail(lambda: module.verify_manifest(manifest, repo, final + b"#tamper\n"), "composed overlay bytes")
    must_fail(lambda: module.verify_manifest(manifest, repo, final, base + b"#stale\n"), "base overlay digest")
    extra = dict(manifest, unexpected="field")
    must_fail(lambda: module.verify_manifest(extra, repo, final), "fields")
    missing = dict(manifest)
    del missing["source_tree"]
    must_fail(lambda: module.verify_manifest(missing, repo, final), "fields")
    malformed = dict(manifest, final_overlay_sha256="not-a-hash")
    must_fail(lambda: module.verify_manifest(malformed, repo, final), "digest is malformed")
    print("PASS tampered bytes, stale base, and malformed manifests fail closed")

    changed = source.replace(b"return view_loader()", b"return changed_loader()")
    (repo / "hermes/sitecustomize.py").write_bytes(changed)
    git(repo, "add", "hermes/sitecustomize.py")
    git(repo, "commit", "-qm", "changed wrapper source")
    must_fail(lambda: module.verify_manifest(manifest, repo, final), "source revision/tree is stale")
    print("PASS stale source revision/tree fails closed")
