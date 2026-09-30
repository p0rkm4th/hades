#!/usr/bin/env python3
"""Check private, no-overwrite behavior of the VM 802 review-candidate builder."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


repo = Path(__file__).resolve().parents[1]
builder_path = repo / "scripts/prepare-vm802-confirmation-review-candidate.py"
spec = importlib.util.spec_from_file_location("confirmation_candidate_builder", builder_path)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

with tempfile.TemporaryDirectory(prefix="hades-review-builder-contract-") as tmp:
    root = Path(tmp)
    root.chmod(0o700)
    private = root / "private"
    private.mkdir(mode=0o700)
    out = private / "candidate.py"
    payload = b"synthetic candidate source\n"
    builder.write_candidate(out, payload)
    assert out.read_bytes() == payload
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    try:
        builder.write_candidate(out, b"overwrite attempt\n")
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing output was overwritten")
    assert out.read_bytes() == payload
    public = root / "public"
    public.mkdir(mode=0o755)
    try:
        builder.write_candidate(public / "candidate.py", payload)
    except ValueError as exc:
        assert "private mode 0700" in str(exc)
    else:
        raise AssertionError("candidate was written below a non-private directory")

    wrong_source = private / "wrong-active.py"
    wrong_source.write_text("not the VM 802 active overlay\n", encoding="utf-8")
    wrong_output = private / "must-not-exist.py"
    result = subprocess.run(
        [sys.executable, str(builder_path), "--active-overlay", str(wrong_source), "--output", str(wrong_output)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode != 0 and "SHA-256 mismatch" in result.stdout, result.stdout
    assert not wrong_output.exists(), "a mismatched base produced a candidate"

print("PASS candidate output is private, mode 0600, no-overwrite, and exact-base-gated")
