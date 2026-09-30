#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import grp
import os
import sqlite3
import stat
import tempfile
from pathlib import Path

from integrations.automation.phase3_self_service import Phase3Error, Phase3Store

group_name = grp.getgrgid(os.getegid()).gr_name
group_id = os.getegid()
with tempfile.TemporaryDirectory(prefix="hades-phase3-shared-state-") as tmp:
    root = Path(tmp)
    private = root / "private" / "phase3.sqlite"
    Phase3Store(str(private))
    assert stat.S_IMODE(private.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(private.stat().st_mode) == 0o600

    shared_dir = root / "shared"
    shared_dir.mkdir(mode=0o700)
    os.chown(shared_dir, -1, group_id)
    os.chmod(shared_dir, 0o2770)
    shared = shared_dir / "phase3.sqlite"
    old = os.environ.get(Phase3Store.SHARED_GROUP_ENV)
    os.environ[Phase3Store.SHARED_GROUP_ENV] = group_name
    try:
        Phase3Store(str(shared))
        with sqlite3.connect(shared) as db:
            db.execute("INSERT INTO phase3_meta(key,value) VALUES(?,?)", ("contract", "shared"))
        Phase3Store(str(shared))
        with sqlite3.connect(shared) as db:
            assert db.execute("SELECT value FROM phase3_meta WHERE key='contract'").fetchone() == ("shared",)
        assert stat.S_IMODE(shared_dir.stat().st_mode) == 0o2770
        assert shared_dir.stat().st_gid == group_id
        assert stat.S_IMODE(shared.stat().st_mode) == 0o660
        assert shared.stat().st_gid == group_id

        shared.chmod(0o600)
        try:
            Phase3Store(str(shared))
        except Phase3Error as exc:
            assert "permissions are unsafe" in str(exc)
        else:
            raise AssertionError("private database was silently widened for group sharing")
        assert stat.S_IMODE(shared.stat().st_mode) == 0o600
    finally:
        if old is None:
            os.environ.pop(Phase3Store.SHARED_GROUP_ENV, None)
        else:
            os.environ[Phase3Store.SHARED_GROUP_ENV] = old

print("PASS Phase 3 state preserves the private default and validates explicit shared-group modes")
PY

image=${HADES_PHASE3_SHARED_STATE_TEST_IMAGE:-}
if [[ -z "$image" ]]; then
  echo 'FAIL set HADES_PHASE3_SHARED_STATE_TEST_IMAGE to an immutable local image ID with Python 3.' >&2
  exit 2
fi
if [[ ! "$image" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo 'FAIL cross-UID test image must be an immutable sha256 image ID' >&2
  exit 1
fi

docker run --rm --user 0:0 --tmpfs /test-state:rw,nosuid,nodev,mode=0755,size=16m \
  --entrypoint python3 \
  -e PYTHONPATH=/repo \
  -v "$PWD:/repo:ro" \
  "$image" /repo/scripts/test-phase3-shared-state-multiuser.py /test-state
