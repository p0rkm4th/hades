#!/usr/bin/env python3
"""Package the private Epsilon source endpoint and its HADES policy modules.

This copies only public source files into an existing generated deployment
root. Private inputs, state, secrets, and unrelated deployment records are
never read or replaced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int, root: Path) -> None:
    if not path.is_relative_to(root):
        raise ValueError("package destination escaped output root")
    current = root
    for part in path.parent.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlink directory: {current}")
        current.mkdir(mode=0o755, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"refusing symlink destination: {path}")
    if path.is_file() and path.read_bytes() == data and (path.stat().st_mode & 0o777) == mode:
        return
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def package(source_root: Path, output_root: Path) -> dict[str, object]:
    source_root = source_root.resolve(strict=True)
    output_root = output_root.resolve(strict=True)
    if not source_root.is_dir() or not output_root.is_dir():
        raise ValueError("source root and existing output root must be directories")
    if output_root.is_relative_to(source_root) or source_root.is_relative_to(output_root):
        raise ValueError("output root must be outside the source checkout")

    source_files = {
        Path("config/epsilon-source/server.py"): source_root / "integrations/epsilon-source/server.py",
        Path("integrations/__init__.py"): source_root / "integrations/__init__.py",
    }
    automation = source_root / "integrations/automation"
    if automation.is_symlink() or not automation.is_dir():
        raise ValueError("HADES automation source package is missing or unsafe")
    for path in sorted(automation.glob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"refusing unsafe automation source: {path}")
        source_files[Path("integrations/automation") / path.name] = path

    records = {}
    for relative, source in sorted(source_files.items()):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"required source is missing or unsafe: {source}")
        data = source.read_bytes()
        records[relative.as_posix()] = {"sha256": sha256(data), "size": len(data)}

    manifest = {
        "schema": 1,
        "package": "hades-epsilon-source",
        "files": records,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()

    for relative, source in sorted(source_files.items()):
        atomic_write(output_root / relative, source.read_bytes(), 0o644, output_root)
    atomic_write(output_root / "config/epsilon-source/phase3-runtime-manifest.json", manifest_bytes, 0o644, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, help="HADES source checkout")
    parser.add_argument("output_root", type=Path, help="existing generated deployment root")
    args = parser.parse_args()
    result = package(args.source_root, args.output_root)
    print(f"PASS packaged {len(result['files'])} Epsilon/HADES source files; private inputs and state untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
