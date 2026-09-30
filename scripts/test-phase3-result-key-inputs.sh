#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import os
import pwd
import grp
import stat
import subprocess
import tempfile
from pathlib import Path

uid = os.geteuid()
user = pwd.getpwuid(uid).pw_name
group = grp.getgrgid(os.getegid()).gr_name
script = Path("scripts/create-phase3-result-query-keys.py").resolve()
with tempfile.TemporaryDirectory(prefix="hades-phase3-keys-") as tmp:
    root = Path(tmp)
    hermes = root / "hermes" / "phase3-result.key"
    epsilon = root / "epsilon" / "phase3-result.key"
    hermes.parent.mkdir(mode=0o700)
    epsilon.parent.mkdir(mode=0o700)
    completed = subprocess.run(
        ["python3", str(script), str(hermes), user, group, str(epsilon), user, group],
        text=True, capture_output=True, check=True,
    )
    assert "synthetic" not in completed.stdout.casefold()
    assert hermes.read_bytes() == epsilon.read_bytes()
    assert 32 <= len(hermes.read_bytes().strip()) <= 256
    for path in (hermes, epsilon):
        info = path.stat()
        assert stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == uid
    prior = hermes.read_bytes()
    failed = subprocess.run(
        ["python3", str(script), str(hermes), user, group, str(root / "other.key"), user, group],
        text=True, capture_output=True,
    )
    assert failed.returncode != 0 and hermes.read_bytes() == prior
    assert not (root / "other.key").exists()

print("PASS Phase 3 result key inputs: distinct service-owned 0600 copies, no overwrite, no secret output")
PY
