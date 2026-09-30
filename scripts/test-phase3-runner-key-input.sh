#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import grp
import os
import pwd
import stat
import subprocess
import tempfile
from pathlib import Path

user = pwd.getpwuid(os.geteuid()).pw_name
group = grp.getgrgid(os.getegid()).gr_name
script = Path("scripts/create-phase3-runner-key.py").resolve()
with tempfile.TemporaryDirectory(prefix="hades-phase3-runner-key-") as tmp:
    root = Path(tmp)
    secure = root / "secure"
    secure.mkdir(mode=0o700)
    path = secure / "runner.key"
    created = subprocess.run(
        ["python3", str(script), str(path), user, group],
        text=True, capture_output=True, check=True,
    )
    key = path.read_bytes().strip()
    assert len(key) == 64 and key.decode().isascii()
    info = path.stat()
    assert stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == os.geteuid()
    assert key.decode() not in created.stdout and key.decode() not in created.stderr
    previous = path.read_bytes()
    failed = subprocess.run(
        ["python3", str(script), str(path), user, group], text=True, capture_output=True,
    )
    assert failed.returncode != 0 and path.read_bytes() == previous
    unsafe = root / "unsafe"
    unsafe.mkdir(mode=0o700)
    unsafe.chmod(0o777)
    refused = subprocess.run(
        ["python3", str(script), str(unsafe / "runner.key"), user, group], text=True, capture_output=True,
    )
    assert refused.returncode != 0 and not (unsafe / "runner.key").exists()
    readable = root / "readable"
    readable.mkdir(mode=0o700)
    readable.chmod(0o755)
    refused = subprocess.run(
        ["python3", str(script), str(readable / "runner.key"), user, group], text=True, capture_output=True,
    )
    assert refused.returncode != 0 and not (readable / "runner.key").exists()

print("PASS Phase 3 runner key input: secure one-time file, service ownership, no overwrite, no secret output")
PY
