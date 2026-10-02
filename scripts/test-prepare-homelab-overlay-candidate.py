#!/usr/bin/env python3
"""Exercise safe, fail-closed homelab overlay composition on synthetic files."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARER = ROOT / "scripts/prepare-homelab-overlay-candidate.py"

SOURCE = '''
import re
def _hades_direct_homelab_read(text, subject="", scope="owner", context_text=""):
    return _hades_homelab_helper(text)
def _hades_homelab_helper(text):
    return text
def _hades_ambiguous_media_device_clarification(text):
    return re.search("device", text)
def _hades_direct_proxmox_backup_read(text, subject="", scope="owner"):
    return text
def _hades_direct_homelab_backup_compound(text, subject="", scope="owner", phase2_session_key=""):
    return text
def _hades_direct_owner_location(text):
    return ""
def _hades_endpoint_continuation_response(text, subject="", scope="owner", context_text=""):
    return text
'''

ACTIVE = '''
import re
_compound_briefing = False
_expiry_response = "expired"
_hades_logger = None
def _hades_direct_homelab_read(text):
    return text
def _hades_ambiguous_media_device_clarification(text):
    return None
def handler(self, user_message, previous_user_text, _preflight_text):
    if self._hades_session_scope == "owner" and _compound_briefing:
        return _hades_direct_homelab_read("homelab status and blockers")
    if self._hades_session_scope == "owner":
        response = _hades_direct_homelab_read(user_message)
    if self._hades_session_scope in {"owner", "household"} and not _compound_briefing:
        if _expiry_response:
            return _hades_direct_grocy_expiry_read()
        if self._hades_session_scope == "owner":
            return "owner"
    if self._hades_session_scope in {"owner", "household"}:
        direct_backup_response = _hades_phase2_backup_response(
            user_message, getattr(self, "_hades_subject", ""),
            self._hades_session_scope, _phase2_session_key,
        )
'''


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(PREPARER), *args], text=True, capture_output=True)


with tempfile.TemporaryDirectory(prefix="hades-overlay-preparer-test-") as raw:
    directory = Path(raw)
    os.chmod(directory, 0o700)
    active = directory / "active.py"
    source = directory / "source.py"
    output = directory / "candidate.py"
    active.write_text(ACTIVE, encoding="utf-8")
    source.write_text(SOURCE, encoding="utf-8")
    result = run("--active-overlay", str(active), "--source", str(source), "--output", str(output))
    assert result.returncode == 0, result.stderr
    candidate = output.read_text(encoding="utf-8")
    compile(candidate, str(output), "exec")
    tree = ast.parse(candidate)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_hades_direct_homelab_read"]
    assert len(calls) == 3, len(calls)
    assert "getattr(self, \"_hades_subject\", \"\")" in candidate
    assert "context_text=previous_user_text" in candidate
    assert "context_text=_hades_intent_text" in candidate
    assert "household_homelab_response" in candidate
    assert "Owner node-activity read failed closed without model invocation" in candidate
    assert 'r"\\bwhat(?:' in candidate
    assert "Owner model-capacity follow-up failed closed without model invocation" in candidate
    assert candidate.index("Owner model-capacity follow-up failed closed without model invocation") < candidate.index(
        "response = _hades_direct_homelab_read(user_message"
    )
    assert "_hades_homelab_target_from_question(user_message)" in candidate
    assert "_hades_ambiguous_media_device_clarification(_preflight_text)" in candidate
    assert "_hades_direct_homelab_backup_compound" in candidate
    assert candidate.index("proxmox_backup_response = _hades_direct_proxmox_backup_read") < candidate.index(
        "compound_status_response = _hades_direct_homelab_backup_compound"
    ) < candidate.index("direct_backup_response = _hades_phase2_backup_response")
    assert output.stat().st_mode & 0o777 == 0o600
    assert active.read_text(encoding="utf-8") == ACTIVE

    # A second run must not overwrite an existing candidate.
    second = run("--active-overlay", str(active), "--source", str(source), "--output", str(output))
    assert second.returncode != 0
    assert "new path" in second.stderr

    # Unknown legacy call shapes fail without creating output.
    changed = directory / "changed.py"
    changed.write_text(ACTIVE.replace('_hades_direct_homelab_read(user_message)', '_hades_direct_homelab_read("changed")'), encoding="utf-8")
    refused = run("--active-overlay", str(changed), "--source", str(source), "--output", str(directory / "refused.py"))
    assert refused.returncode != 0
    assert "unrecognized active homelab call" in refused.stderr
    assert not (directory / "refused.py").exists()

print("PASS synthetic focused overlay composition, permissions, preservation, idempotent refusal, and drift refusal")
