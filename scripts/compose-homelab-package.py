#!/usr/bin/env python3
"""Compose an exact, importable homelab MCP package from a clean HADES Git tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


PACKAGE_PREFIX = "integrations/homelab-readonly/"


def git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ValueError("could not inspect the requested HADES Git revision")
    return result.stdout if binary else result.stdout.decode("utf-8", errors="strict").strip()


def canonical_repo(value: Path) -> Path:
    if not value.is_absolute():
        raise ValueError("source repository path must be absolute")
    resolved = value.resolve(strict=True)
    if value != resolved or not resolved.is_dir():
        raise ValueError("source repository must be a real directory without symlink aliases")
    if git(resolved, "rev-parse", "--show-toplevel") != str(resolved):
        raise ValueError("source path is not the HADES Git checkout root")
    return resolved


def tracked_package(repo: Path, revision: str) -> list[tuple[str, str]]:
    raw = git(repo, "ls-tree", "-r", "-z", revision, "--", PACKAGE_PREFIX, binary=True)
    assert isinstance(raw, bytes)
    entries: list[tuple[str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", errors="strict")
        relative = path.removeprefix(PACKAGE_PREFIX)
        if (
            kind != "blob" or mode not in {"100644", "100755"}
            or not relative or "/" in relative or not relative.endswith(".py")
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", relative)
        ):
            raise ValueError("tracked homelab package contains an unsupported path or file type")
        entries.append((relative, blob))
    entries.sort()
    if not entries or len({name for name, _ in entries}) != len(entries):
        raise ValueError("tracked homelab package is empty or has duplicate names")
    return entries


def checked_destination(value: Path, repo: Path) -> tuple[Path, Path]:
    if not value.is_absolute():
        raise ValueError("package output path must be absolute")
    parent = value.parent.resolve(strict=True)
    if value.parent != parent or not parent.is_dir():
        raise ValueError("package output parent must exist and must not use symlink aliases")
    if parent.stat().st_mode & 0o022:
        raise ValueError("package output parent may not be group/world writable")
    destination = parent / value.name
    if destination.exists() or destination.is_symlink():
        raise ValueError("package output directory already exists")
    if destination == repo or destination.is_relative_to(repo) or repo.is_relative_to(destination):
        raise ValueError("package output must be separate from the HADES source checkout")
    return destination, parent


def compose(source: Path, revision: str, output: Path, manifest: Path | None) -> Path:
    repo = canonical_repo(source)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("source revision must be a full lowercase Git commit SHA")
    actual_revision = git(repo, "rev-parse", "HEAD")
    if actual_revision != revision:
        raise ValueError("source checkout HEAD does not match the requested revision")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source checkout must be clean, including untracked files")
    if git(repo, "rev-parse", f"{revision}^{{commit}}") != revision:
        raise ValueError("requested source revision is not an exact commit")

    entries = tracked_package(repo, revision)
    destination, parent = checked_destination(output, repo)
    if manifest is None:
        manifest = parent / f"{destination.name}.manifest.json"
    if not manifest.is_absolute():
        raise ValueError("manifest path must be absolute")
    manifest_parent = manifest.parent.resolve(strict=True)
    if manifest.parent != manifest_parent or not manifest_parent.is_dir():
        raise ValueError("manifest parent must exist and must not use symlink aliases")
    if manifest_parent.stat().st_mode & 0o022:
        raise ValueError("manifest parent may not be group/world writable")
    manifest = manifest_parent / manifest.name
    if manifest.exists() or manifest.is_symlink():
        raise ValueError("manifest output already exists")
    if (
        manifest.is_relative_to(destination)
        or manifest == repo
        or manifest.is_relative_to(repo)
        or repo.is_relative_to(manifest)
    ):
        raise ValueError("manifest must be outside the import package and source checkout")

    tree = git(repo, "rev-parse", f"{revision}:integrations/homelab-readonly")
    temp_dir: Path | None = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=parent))
    temp_manifest: Path | None = None
    published_package = False
    published_manifest = False
    try:
        os.chmod(temp_dir, 0o750)
        records = []
        for name, blob in entries:
            content = git(repo, "cat-file", "blob", blob, binary=True)
            assert isinstance(content, bytes)
            file_path = temp_dir / name
            with file_path.open("xb") as stream:
                stream.write(content)
            os.chmod(file_path, 0o640)
            records.append({
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            })
        manifest_obj = {
            "schema": "hades/homelab-package/v1",
            "source_revision": revision,
            "source_tree": tree,
            "files": records,
        }
        encoded = (json.dumps(manifest_obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
        manifest_obj["package_sha256"] = hashlib.sha256(encoded.rstrip(b"\n")).hexdigest()
        encoded = (json.dumps(manifest_obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd, name = tempfile.mkstemp(prefix=f".{manifest.name}.", dir=manifest_parent)
        temp_manifest = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        os.chmod(temp_manifest, 0o600)
        if destination.exists() or destination.is_symlink() or manifest.exists() or manifest.is_symlink():
            raise ValueError("package or manifest output appeared during composition")
        os.rename(temp_dir, destination)
        temp_dir = None
        published_package = True
        os.rename(temp_manifest, manifest)
        temp_manifest = None
        published_manifest = True
        return manifest
    finally:
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir)
        if temp_manifest is not None and temp_manifest.exists():
            temp_manifest.unlink()
        if published_package and not published_manifest and destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, help="absolute manifest path outside the package (default: sibling .manifest.json)")
    args = parser.parse_args()
    try:
        manifest = compose(args.source_repo, args.revision, args.output, args.manifest)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"PASS homelab package composed: {len(list(args.output.glob('*.py')))} modules; manifest SHA-256 {hashlib.sha256(manifest.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
