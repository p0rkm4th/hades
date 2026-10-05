#!/usr/bin/env python3
"""Synthetic contracts for the deployment-local homelab overlay composer."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare-homelab-overlay-candidate.py"
spec = importlib.util.spec_from_file_location("homelab_overlay_composer", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def must_fail(active: bytes, source: bytes, message: str) -> None:
    try:
        module.compose(active, source, "active.py", "source.py")
    except SystemExit as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"expected failure containing {message!r}")


active = '''# deployment-local prefix sentinel
LOCAL_SETTING = "preserve-this"

def _hades_load_homelab_views():
    return local_view_loader()

def _hades_homelab_guest_visibility_response(summary):
    return "old guest renderer"

# interstitial deployment-local sentinel
LOCAL_MARKER = "preserve-π"

def _hades_household_homelab_boundary_response(user_text):
    return "old household renderer"

# deployment-local suffix sentinel
'''.encode()
source = b'''def _hades_load_homelab_views():
    return candidate_view_loader()

def _hades_homelab_guest_visibility_response(summary):
    return _hades_load_homelab_views().guest(summary)

def _hades_household_homelab_boundary_response(user_text):
    return _hades_load_homelab_views().household(user_text)
'''

# These literal regions are intentionally independent of the composer parser.
active_prefix = b'''# deployment-local prefix sentinel
LOCAL_SETTING = "preserve-this"

def _hades_load_homelab_views():
    return local_view_loader()

'''
active_middle = '''
# interstitial deployment-local sentinel
LOCAL_MARKER = "preserve-π"

'''.encode()
active_suffix = b'''
# deployment-local suffix sentinel
'''
source_guest = b'''def _hades_homelab_guest_visibility_response(summary):
    return _hades_load_homelab_views().guest(summary)
'''
source_household = b'''def _hades_household_homelab_boundary_response(user_text):
    return _hades_load_homelab_views().household(user_text)
'''
expected = active_prefix + source_guest + active_middle + source_household + active_suffix

candidate = module.compose(active, source, "active.py", "source.py")
assert candidate == expected
compile(candidate, "synthetic-active-overlay.py", "exec")
assert "LOCAL_MARKER = \"preserve-π\"".encode() in candidate
print("PASS exact wrapper replacement preserves every other overlay byte")

# Also source the exact two definitions from this candidate's sitecustomize.py.
tracked_source = (ROOT / "hermes/sitecustomize.py").read_bytes()
tracked_spans = module.source_spans(
    tracked_source, "hermes/sitecustomize.py", module.FUNCTIONS, True
)
tracked_guest = tracked_source[slice(*tracked_spans[module.FUNCTIONS[0]])]
tracked_household = tracked_source[slice(*tracked_spans[module.FUNCTIONS[1]])]
candidate_from_tracked = module.compose(
    active, tracked_source, "active.py", "hermes/sitecustomize.py"
)
expected_tracked = active_prefix + tracked_guest + active_middle + tracked_household + active_suffix
assert candidate_from_tracked == expected_tracked
assert b"deployment-local prefix sentinel" in candidate_from_tracked
assert b"deployment-local suffix sentinel" in candidate_from_tracked
print("PASS exact tracked helper definitions compose over a local overlay unchanged elsewhere")

missing_household = source.replace(source_household, b"")
must_fail(active, missing_household, "exactly one top-level _hades_household_homelab_boundary_response")
duplicate_guest = active + b"\ndef _hades_homelab_guest_visibility_response(summary):\n    return None\n"
must_fail(duplicate_guest, source, "exactly one top-level _hades_homelab_guest_visibility_response")
missing_loader = active.replace(
    b"def _hades_load_homelab_views():\n    return local_view_loader()\n\n", b""
)
must_fail(missing_loader, source, "exactly one top-level _hades_load_homelab_views")
no_loader_call = source.replace(
    b"return _hades_load_homelab_views().guest(summary)", b"return None"
)
must_fail(active, no_loader_call, "does not use the compatibility loader")
malformed = active + b"\ndef broken(:\n"
must_fail(malformed, source, "not valid UTF-8 Python")
print("PASS missing, duplicate, malformed, and loaderless cases fail closed")

with tempfile.TemporaryDirectory(prefix="hades-overlay-composer-") as temporary:
    root = Path(temporary)
    active_path = root / "active.py"
    source_path = root / "source.py"
    output_path = root / "candidate.py"
    active_path.write_bytes(active)
    source_path.write_bytes(source)
    os.chmod(active_path, 0o600)
    os.chmod(source_path, 0o600)
    command = [
        sys.executable, os.fspath(SCRIPT), "--active-overlay", os.fspath(active_path),
        "--source", os.fspath(source_path), "--output", os.fspath(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert output_path.read_bytes() == expected
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    before = output_path.read_bytes()
    failed = subprocess.run(command, capture_output=True, text=True)
    assert failed.returncode != 0 and "must be a new path" in failed.stderr
    assert output_path.read_bytes() == before
print("PASS CLI writes mode-0600 candidate and refuses output overwrite")
