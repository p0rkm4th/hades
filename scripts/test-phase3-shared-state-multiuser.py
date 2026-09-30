#!/usr/bin/env python3
"""Prove Phase3Store survives access and restart across distinct service UIDs."""

from __future__ import annotations

import grp
import os
import sqlite3
import stat
import sys
import time
from multiprocessing import get_context
from pathlib import Path

from integrations.automation.phase3_self_service import Phase3Store


if os.geteuid() != 0:
    raise SystemExit("cross-UID shared-state test must run as root in its disposable container")
state_root = Path(sys.argv[1]).resolve(strict=True)
group_name = "hades-phase3-contract"
gid = 45000 + (os.getpid() % 10000)
while True:
    try:
        grp.getgrgid(gid)
    except KeyError:
        break
    gid += 1
with open("/etc/group", "a", encoding="utf-8") as stream:
    stream.write(f"{group_name}:x:{gid}:\n")

shared_dir = state_root / "shared"
shared_dir.mkdir(mode=0o700)
os.chown(shared_dir, 0, gid)
os.chmod(shared_dir, 0o2770)
database = shared_dir / "phase3.sqlite"
os.environ[Phase3Store.SHARED_GROUP_ENV] = group_name


def become_service(uid: int) -> None:
    os.umask(0o007)
    os.setgroups([gid])
    os.setgid(gid)
    os.setuid(uid)


def create_as(uid: int, ready, release) -> None:
    become_service(uid)
    Phase3Store(str(database))
    connection = sqlite3.connect(database, isolation_level=None, timeout=5)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO phase3_meta(key,value) VALUES('cross-uid','writer-a')"
        )
        ready.set()
        if not release.wait(10):
            raise TimeoutError("test release was not signalled")
        connection.execute("COMMIT")
    finally:
        connection.close()


def update_as(uid: int) -> None:
    become_service(uid)
    store = Phase3Store(str(database))
    with sqlite3.connect(store.path, timeout=5) as connection:
        assert connection.execute(
            "SELECT value FROM phase3_meta WHERE key='cross-uid'"
        ).fetchone() == ("writer-a",)
        connection.execute(
            "UPDATE phase3_meta SET value='writer-b' WHERE key='cross-uid'"
        )


def verify_as(uid: int, expected: str) -> None:
    become_service(uid)
    store = Phase3Store(str(database))
    with sqlite3.connect(store.path, timeout=5) as connection:
        assert connection.execute(
            "SELECT value FROM phase3_meta WHERE key='cross-uid'"
        ).fetchone() == (expected,)


ctx = get_context("fork")
bootstrap_database = shared_dir / "simultaneous-bootstrap.sqlite"
bootstrap_barrier = ctx.Barrier(3)


def initialize_as(uid: int, marker: str) -> None:
    become_service(uid)
    bootstrap_barrier.wait(timeout=10)
    store = Phase3Store(str(bootstrap_database))
    with sqlite3.connect(store.path, timeout=5) as connection:
        connection.execute(
            "INSERT INTO phase3_meta(key,value) VALUES(?,?)", (marker, "ready")
        )


bootstrap_processes = [
    ctx.Process(target=initialize_as, args=(uid, f"uid-{uid}"))
    for uid in (21001, 21002)
]
for process in bootstrap_processes:
    process.start()
bootstrap_barrier.wait(timeout=10)
for process in bootstrap_processes:
    process.join(15)
    if process.exitcode != 0:
        raise SystemExit("simultaneous Phase 3 state initialization failed")
with sqlite3.connect(bootstrap_database) as connection:
    assert connection.execute(
        "SELECT COUNT(*) FROM phase3_meta WHERE value='ready'"
    ).fetchone() == (2,)

ready = ctx.Event()
release = ctx.Event()
writer = ctx.Process(target=create_as, args=(21001, ready, release))
writer.start()
if not ready.wait(10):
    raise SystemExit("first service UID did not acquire the shared database")

journal = Path(str(database) + "-journal")
deadline = time.monotonic() + 2
while time.monotonic() < deadline and not journal.exists():
    time.sleep(0.01)
if journal.exists():
    journal_info = journal.stat()
    if journal_info.st_gid != gid or stat.S_IMODE(journal_info.st_mode) & 0o060 != 0o060:
        release.set()
        writer.join(10)
        raise SystemExit("SQLite rollback journal is not group-readable and writable")
release.set()
writer.join(10)
if writer.exitcode != 0:
    raise SystemExit("first service UID failed to commit its Phase 3 state")

updater = ctx.Process(target=update_as, args=(21002,))
updater.start()
updater.join(10)
if updater.exitcode != 0:
    raise SystemExit("second service UID could not read/update Phase 3 state")

restarted_reader = ctx.Process(target=verify_as, args=(21001, "writer-b"))
restarted_reader.start()
restarted_reader.join(10)
if restarted_reader.exitcode != 0:
    raise SystemExit("first service UID could not read state after the other UID wrote it")

info = database.stat()
if info.st_gid != gid or stat.S_IMODE(info.st_mode) != Phase3Store.SHARED_DATABASE_MODE:
    raise SystemExit("shared Phase 3 database permissions drifted")
if stat.S_IMODE(shared_dir.stat().st_mode) != Phase3Store.SHARED_DIRECTORY_MODE:
    raise SystemExit("shared Phase 3 directory permissions drifted")
print("PASS Phase 3 SQLite state is readable/writable across two service UIDs and survives process restart")
