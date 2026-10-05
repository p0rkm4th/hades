#!/usr/bin/env python3
"""Synthetic contract for source-bound Hermes overlay composition."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts/prepare-homelab-overlay-candidate.py"
MANIFEST_TOOL = ROOT / "scripts/hermes-overlay-composition.py"
PROVENANCE = ROOT / "scripts/write-deployed-provenance.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True)
    return result.stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", ".gitignore", "hermes/sitecustomize.py", "scripts/prepare-homelab-overlay-candidate.py", "scripts/hermes-overlay-composition.py")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def must_fail(call, phrase: str) -> None:
    try:
        call()
    except (ValueError, SystemExit) as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected failure containing {phrase!r}")


with tempfile.TemporaryDirectory(prefix="hades-overlay-manifest-") as temp:
    root = Path(temp)
    repo = root / "source"
    (repo / "hermes").mkdir(parents=True)
    (repo / "scripts").mkdir()
    shutil.copyfile(COMPOSER, repo / "scripts/prepare-homelab-overlay-candidate.py")
    shutil.copyfile(MANIFEST_TOOL, repo / "scripts/hermes-overlay-composition.py")
    source = b'''def _hades_load_homelab_views():\n    return view_loader()\n\ndef _hades_homelab_guest_visibility_response(summary):\n    return _hades_load_homelab_views().guest(summary)\n\ndef _hades_household_homelab_boundary_response(user_text, conversation_history=None):\n    return deny_household(user_text, conversation_history)\n'''
    source_path = repo / "hermes/sitecustomize.py"
    source_path.write_bytes(source)
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "synthetic@example.invalid")
    git(repo, "config", "user.name", "Synthetic Test")
    revision = commit(repo, "fixture")

    composer = load(repo / "scripts/prepare-homelab-overlay-candidate.py", "fixture_composer")
    base = b'''# deployment-local sentinel\nPRIVATE_POLICY_SENTINEL = "keep exact bytes"\ndef _hades_load_homelab_views():\n    return view_loader()\ndef _hades_homelab_guest_visibility_response(summary):\n    return old_guest(summary)\ndef _hades_household_homelab_boundary_response(user_text, conversation_history=None):\n    return local_household_policy(user_text, conversation_history)\n'''
    final = composer.compose(base, source)
    active_span = composer.source_spans(base, "base", composer.FUNCTIONS)["_hades_homelab_guest_visibility_response"]
    source_span = composer.source_spans(source, "source", composer.FUNCTIONS, True)["_hades_homelab_guest_visibility_response"]
    replacement = source[source_span[0]:source_span[1]]
    assert final[:active_span[0]] == base[:active_span[0]]
    assert final[active_span[0]:active_span[0] + len(replacement)] == replacement
    assert final[active_span[0] + len(replacement):] == base[active_span[1]:]
    assert b'PRIVATE_POLICY_SENTINEL = "keep exact bytes"' in final
    assert b"return local_household_policy(user_text, conversation_history)" in final
    assert b"return _hades_load_homelab_views().guest(summary)" in final
    manifest_tool = load(repo / "scripts/hermes-overlay-composition.py", "fixture_manifest")
    manifest = manifest_tool.build_manifest(repo, base, final)
    assert manifest["source_revision"] == revision
    assert set(manifest["wrapper_sha256"]) == {"_hades_homelab_guest_visibility_response"}
    assert set(manifest) == manifest_tool.FIELDS
    assert str(repo).encode() not in json.dumps(manifest).encode()
    assert "PRIVATE_POLICY_SENTINEL" not in json.dumps(manifest)
    assert "synthetic-only" not in json.dumps(manifest)
    assert manifest_tool.verify_manifest(manifest, repo, final, base)
    assert manifest_tool.verify_manifest(manifest, repo, final, final)  # idempotent revalidation

    base_path, final_path, output_path = root / "active.py", root / "candidate.py", root / "record.json"
    base_path.write_bytes(base)
    final_path.write_bytes(final)
    subprocess.run([
        os.environ.get("PYTHON", "python3"), str(MANIFEST_TOOL),
        "--source-repo", str(repo), "--base-overlay", str(base_path),
        "--final-overlay", str(final_path), "--output", str(output_path),
    ], check=True, capture_output=True, text=True)
    assert output_path.stat().st_mode & 0o777 == 0o600
    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest
    refused = subprocess.run([
        os.environ.get("PYTHON", "python3"), str(MANIFEST_TOOL),
        "--source-repo", str(repo), "--base-overlay", str(base_path),
        "--final-overlay", str(final_path), "--output", str(output_path),
    ], check=False, capture_output=True, text=True)
    assert refused.returncode != 0

    provenance = load(PROVENANCE, "fixture_provenance")
    manifest_path = root / "composition.json"
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    # The provenance writer reads stable files; exercise its integration with real synthetic artifacts.
    (root / "base.py").write_bytes(base)
    loaded, recorded_sha, _ = provenance.load_overlay_composition(manifest_path, root / "base.py", repo, final)
    assert loaded == manifest and recorded_sha == hashlib.sha256(manifest_bytes).hexdigest()
    must_fail(
        lambda: provenance.load_overlay_composition(manifest_path, root / "base.py", repo, final + b"# tamper\n"),
        "does not match",
    )

    tampered = final + b"# changed\n"
    must_fail(lambda: manifest_tool.verify_manifest(manifest, repo, tampered, base), "differ")
    must_fail(lambda: manifest_tool.verify_manifest({**manifest, "unexpected": True}, repo, final, base), "fields")
    must_fail(lambda: manifest_tool.verify_manifest({**manifest, "wrapper_sha256": {}}, repo, final, base), "wrapper")
    must_fail(lambda: manifest_tool.verify_manifest({**manifest, "final_overlay_sha256": "bad"}, repo, final, base), "digest")
    wrong_base = base + b"# stale\n"
    must_fail(lambda: manifest_tool.verify_manifest(manifest, repo, final, wrong_base), "base overlay")

    source_path.write_bytes(source.replace(b"_hades_load_homelab_views().guest", b"other_loader().guest"))
    must_fail(lambda: manifest_tool.verify_manifest(manifest, repo, final, base), "clean")
    git(repo, "checkout", "--", "hermes/sitecustomize.py")
    git(repo, "commit", "--allow-empty", "-qm", "advance source revision")
    must_fail(lambda: manifest_tool.verify_manifest(manifest, repo, final, base), "revision/tree")

    duplicate = source + b"\ndef _hades_homelab_guest_visibility_response(summary):\n    return None\n"
    must_fail(lambda: composer.compose(base, duplicate), "exactly one")
    missing_target = source.replace(
        b"def _hades_homelab_guest_visibility_response(summary):\n    return _hades_load_homelab_views().guest(summary)\n", b""
    )
    must_fail(lambda: composer.compose(base, missing_target), "exactly one")
    missing_loader = source.replace(b"_hades_load_homelab_views().guest", b"view_loader().guest")
    must_fail(lambda: composer.compose(base, missing_loader), "compatibility loader")

print("PASS source-bound Hermes overlay composition and provenance integration")
