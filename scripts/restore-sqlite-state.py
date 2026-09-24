#!/usr/bin/env python3
"""Apply the supported HADES SQLite checkpoint to an already-prepared target."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path


FILES = {
    "Open WebUI": ("open-webui.db", "open-webui-data/webui.db"),
    "LLDAP": ("lldap-users.db", "lldap-data/users.db"),
    "Grocy": ("grocy.db", "grocy-config/grocy.db"),
    "Hermes": ("hermes-state.db", "hermes-profile/state.db"),
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL {message}")


def safe_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        fail(f"unsafe or missing file: {path.name}")
    mode = path.stat().st_mode & 0o777
    if mode not in (0o600, 0o640, 0o660):
        fail(f"checkpoint permissions for {path.name}: {mode:o}")


def integrity(path: Path) -> None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as exc:
        fail(f"SQLite integrity check failed for {path.name}: {type(exc).__name__}")
    if result != "ok":
        fail(f"SQLite integrity check failed for {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    target = args.target
    if not args.confirm:
        fail("SQLite restore requires --confirm")
    if not checkpoint.is_dir() or checkpoint.is_symlink():
        fail("checkpoint must be an existing non-symlink directory")
    if not target.is_dir() or target.is_symlink() or not target.is_absolute():
        fail("target must be an existing absolute non-symlink directory")
    if target == Path("/"):
        fail("target must not be the filesystem root")

    sources: dict[str, Path] = {}
    destinations: dict[str, Path] = {}
    for label, (source_name, relative_target) in FILES.items():
        source = checkpoint / source_name
        destination = target / relative_target
        safe_file(source)
        if any(parent.is_symlink() for parent in (target, destination.parent)):
            fail(f"prepared target contains a symlink for {label}")
        if destination.is_symlink() or not destination.is_file():
            fail(f"prepared target missing or unsafe for {label}")
        if destination.stat().st_mode & 0o777 not in (0o600, 0o640, 0o660):
            fail(f"target permissions for {label} are too broad")
        integrity(source)
        sources[label] = source
        destinations[label] = destination

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    rollback = target / f".hades-pre-restore-{stamp}-{os.getpid()}"
    rollback.mkdir(mode=0o700)
    replaced: list[tuple[Path, Path]] = []
    try:
        for label, source in sources.items():
            destination = destinations[label]
            saved = rollback / destination.name
            shutil.copy2(destination, saved)
            os.chmod(saved, 0o600)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                with source.open("rb") as source_file:
                    shutil.copyfileobj(source_file, temporary)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, destination)
            replaced.append((destination, saved))
            print(f"PASS restored {label} SQLite state")
    except Exception as exc:
        for destination, saved in reversed(replaced):
            os.replace(saved, destination)
        shutil.rmtree(rollback, ignore_errors=True)
        fail(f"restore rolled back: {type(exc).__name__}")

    print(f"PASS rollback checkpoint retained: {rollback}")
    print("REVIEW Hindsight/PostgreSQL, Agent Zero, SearXNG, secrets, and canonical external apps require native restore procedures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
