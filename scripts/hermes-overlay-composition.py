#!/usr/bin/env python3
"""Build and verify a source-bound manifest for a composed Hermes overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from types import ModuleType
from pathlib import Path
from typing import Any

SCHEMA = "hades/hermes-overlay-composition/v1"
SOURCE_RELATIVE = "hermes/sitecustomize.py"
COMPOSER_RELATIVE = "scripts/prepare-homelab-overlay-candidate.py"
MANIFEST_RELATIVE = "scripts/hermes-overlay-composition.py"
FUNCTIONS = ("_hades_homelab_guest_visibility_response",)
FIELDS = {"schema", "source_revision", "source_tree", "base_overlay_sha256", "wrapper_sha256", "final_overlay_sha256"}
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path) -> bytes:
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("not regular")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        data = b"".join(chunks)
        if before_id != after_id or len(data) != after.st_size:
            raise OSError("changed while reading")
        return data
    except (OSError, RuntimeError, ValueError):
        raise ValueError("required regular file is unavailable or changed") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("source repository identity is unavailable") from None
    return result.stdout.strip()


def _tracked_file_bytes(repo: Path, relative: str) -> bytes:
    """Return a stable working file only when it exactly matches a regular Git blob."""
    root = Path(repo).resolve(strict=True)
    target = root / relative
    current = root
    for part in Path(relative).parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise ValueError("tracked source path is not a regular repository path")
    try:
        tree_line = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-z", "HEAD", "--", relative],
            check=True, capture_output=True,
        ).stdout
        records = [record for record in tree_line.split(b"\0") if record]
        if len(records) != 1:
            raise ValueError("tracked source is absent or ambiguous")
        metadata, listed_path = records[0].split(b"\t", 1)
        mode, kind, _object_id = metadata.decode("ascii").split()
        if listed_path.decode("utf-8", errors="strict") != relative or mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError("tracked source is not a regular Git file")
        expected = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relative}"],
            check=True, capture_output=True,
        ).stdout
        actual = read_regular(target)
    except (OSError, UnicodeError, subprocess.CalledProcessError, ValueError):
        raise ValueError("tracked source bytes are unavailable or unsafe") from None
    if actual != expected:
        raise ValueError("working source bytes differ from the exact Git blob")
    return actual


def _tracked_source(repo: Path) -> tuple[str, str, bytes]:
    repo = Path(repo)
    if repo.is_symlink() or not repo.is_dir():
        raise ValueError("source repository must be a real Git worktree")
    root = repo.resolve(strict=True)
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("source path must be the Git worktree root")
    revision = _git(root, "rev-parse", "--verify", "HEAD")
    tree = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
    if not _GIT_SHA.fullmatch(revision) or not _GIT_SHA.fullmatch(tree):
        raise ValueError("source repository identity is malformed")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source repository must be clean")
    try:
        source = _tracked_file_bytes(root, SOURCE_RELATIVE)
        _tracked_file_bytes(root, COMPOSER_RELATIVE)
        recorded_manifest_tool = _tracked_file_bytes(root, MANIFEST_RELATIVE)
        running_manifest_tool = read_regular(Path(__file__))
    except ValueError:
        raise ValueError("tracked overlay source or composer is unavailable") from None
    if running_manifest_tool != recorded_manifest_tool:
        raise ValueError("running manifest verifier differs from the exact Git blob")
    return revision, tree, source


def _composer(repo: Path):
    source = _tracked_file_bytes(repo, COMPOSER_RELATIVE)
    module = ModuleType("_hades_overlay_composer")
    module.__file__ = str(Path(repo) / COMPOSER_RELATIVE)
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _wrapper_hashes(source: bytes, repo: Path) -> dict[str, str]:
    composer = _composer(repo)
    spans = composer.source_spans(source, SOURCE_RELATIVE, FUNCTIONS, True)
    return {name: _sha256(source[start:end]) for name, (start, end) in spans.items()}


def build_manifest(repo: Path, base_overlay: bytes, final_overlay: bytes) -> dict[str, Any]:
    repo = Path(repo).resolve(strict=True)
    revision, tree, source = _tracked_source(repo)
    composer = _composer(repo)
    expected = composer.compose(base_overlay, source, "base overlay", SOURCE_RELATIVE)
    if expected != final_overlay:
        raise ValueError("final overlay is not the exact tracked-wrapper composition")
    spans = composer.source_spans(source, SOURCE_RELATIVE, FUNCTIONS, True)
    return {
        "schema": SCHEMA,
        "source_revision": revision,
        "source_tree": tree,
        "base_overlay_sha256": _sha256(base_overlay),
        "wrapper_sha256": {name: _sha256(source[start:end]) for name, (start, end) in spans.items()},
        "final_overlay_sha256": _sha256(final_overlay),
    }


def verify_manifest(manifest: Any, repo: Path, final_overlay: bytes, base_overlay: bytes) -> bool:
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise ValueError("composition manifest fields do not match schema")
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
        not isinstance(v, str) or not _SHA256.fullmatch(v) for v in hashes.values()
    ):
        raise ValueError("composition manifest wrapper digests are malformed")
    repo = Path(repo).resolve(strict=True)
    revision, tree, source = _tracked_source(repo)
    if manifest["source_revision"] != revision or manifest["source_tree"] != tree:
        raise ValueError("composition manifest source revision/tree is stale")
    if manifest["wrapper_sha256"] != _wrapper_hashes(source, repo):
        raise ValueError("composition manifest wrapper digest is stale")
    if _sha256(final_overlay) != manifest["final_overlay_sha256"]:
        raise ValueError("composed overlay bytes differ from manifest")
    if _sha256(base_overlay) != manifest["base_overlay_sha256"]:
        if _sha256(base_overlay) != manifest["final_overlay_sha256"]:
            raise ValueError("base overlay digest differs from manifest")
    composer = _composer(repo)
    if composer.compose(base_overlay, source, "base overlay", SOURCE_RELATIVE) != final_overlay:
        raise ValueError("base overlay does not compose to recorded final bytes")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--base-overlay", type=Path, required=True)
    parser.add_argument("--final-overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not args.output.is_absolute():
            raise ValueError("manifest output must be an absolute path")
        output_parent = args.output.parent.resolve(strict=True)
        if args.output.parent != output_parent or output_parent.stat().st_mode & 0o022:
            raise ValueError("manifest output parent must be canonical and protected")
        output = output_parent / args.output.name
        if output.exists() or output.is_symlink():
            raise ValueError("manifest output must not already exist")
        base = read_regular(args.base_overlay)
        final = read_regular(args.final_overlay)
        manifest = build_manifest(args.source_repo, base, final)
        data = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output_parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if output.exists() or output.is_symlink():
                raise ValueError("manifest output must not already exist")
            os.link(temporary, output, follow_symlinks=False)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, ValueError, SystemExit) as exc:
        raise SystemExit("FAIL overlay composition manifest was not written") from None
    print("PASS overlay composition manifest written (mode=0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
