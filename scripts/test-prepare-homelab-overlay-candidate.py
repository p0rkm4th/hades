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
import re, time
from datetime import datetime
def _hades_direct_homelab_read(text, subject="", scope="owner", context_text=""):
    if _hades_service_health_target(text):
        return text
    return _hades_homelab_helper(text)
def _hades_homelab_recent_activity_response(report):
    return str(report)
def _hades_service_health_target(text):
    return text if "down" in text.casefold() else None
def _hades_homelab_helper(text):
    datetime.fromisoformat(text)
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
def _hades_is_hermes_auxiliary_prompt(text):
    return False
def _hades_household_game_health_intent(text, scope):
    return False
def _hades_service_placement_intent(text, scope):
    return scope in {"owner", "household"} and "where" in text.casefold()
def _hades_monitor_question_is_diagnostic(text):
    return str(text).lstrip().casefold().startswith("why")
def _hades_health_watch_intent(text):
    return not _hades_monitor_question_is_diagnostic(text)
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
def _hades_monitor_question_is_diagnostic(text):
    return False
def _hades_health_watch_intent(text):
    return True
def _hades_run_conversation(self, user_message, previous_user_text, _preflight_text):
    if _hades_household_game_health_intent(
        user_message, getattr(self, "_hades_session_scope", "")
    ):
        game_health_response = _hades_direct_homelab_read(
            user_message, getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
        )
        if game_health_response:
            return game_health_response
    if _server_actor_turn and _server_status_turn:
        return "managed-server-status"
    turn_started = time.perf_counter()
    if self._hades_session_scope == "owner":
        response = _hades_direct_homelab_read(user_message)
    if self._hades_session_scope in {"owner", "household"} and not _compound_briefing:
        if _expiry_response:
            return _hades_direct_grocy_expiry_read()
        if self._hades_session_scope == "owner":
            return "owner"
    if self._hades_session_scope in {"owner", "household"}:
        _backup_response = _hades_phase2_backup_response(
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
    assert len(calls) == 8, len(calls)
    assert "getattr(self, \"_hades_subject\", \"\")" in candidate
    assert "context_text=previous_user_text" in candidate
    assert "context_text=_hades_intent_text" in candidate
    assert "household_homelab_response" in candidate
    assert "Owner node-activity read failed closed without model invocation" in candidate
    assert "_hades_homelab_named_check_target(user_message)" in candidate
    assert 'r"\\bwhat(?:' in candidate
    assert "Owner model-capacity follow-up failed closed without model invocation" in candidate
    assert "Household game-server health read completed before managed-server routing" in candidate
    assert "Household service-health boundary completed before staged automation routing" in candidate
    assert "_hades_service_health_target(user_message)" in candidate
    assert 'getattr(self, "_hades_session_scope", "")' in candidate
    run_start = candidate.index("def _hades_run_conversation")
    capacity_guard = candidate.index("Owner model-capacity follow-up failed closed without model invocation", run_start)
    game_guard = candidate.index("Household game-server health read completed before managed-server routing", run_start)
    placement_guard = candidate.index("Service-placement inventory read completed before managed-server routing", run_start)
    managed_status_guard = candidate.index("if _server_actor_turn and _server_status_turn", run_start)
    owner_homelab_guard = candidate.index("Owner direct homelab read completed before managed-server routing", run_start)
    household_homelab_guard = candidate.index("Household direct homelab boundary completed before managed-server routing", run_start)
    owner_backup_guard = candidate.index("Owner Proxmox backup read completed before managed-server routing", run_start)
    assert owner_homelab_guard < managed_status_guard
    assert household_homelab_guard < managed_status_guard
    assert owner_backup_guard < owner_homelab_guard
    assert placement_guard < managed_status_guard
    placement_block = candidate[candidate.rfind("if getattr(self, \"_hades_session_scope\", \"\") in {\"owner\", \"household\"} and _hades_service_placement_intent(", run_start):game_guard]
    assert "previous_user_text" not in placement_block
    assert game_guard < candidate.index("turn_started = time.perf_counter()", run_start)
    assert game_guard < capacity_guard
    assert capacity_guard < candidate.index("turn_started = time.perf_counter()", run_start)
    assert capacity_guard < candidate.index("response = _hades_direct_homelab_read(user_message", run_start)
    assert candidate.index("response = _hades_direct_homelab_read(user_message") < candidate.index(
        "Owner node-activity read failed closed without model invocation"
    )
    assert "_hades_homelab_target_from_question(user_message)" in candidate
    assert "_hades_ambiguous_media_device_clarification(_preflight_text)" in candidate
    assert "_hades_direct_homelab_backup_compound" in candidate
    assert "return not _hades_monitor_question_is_diagnostic(text)" in candidate
    assert 'return str(text).lstrip().casefold().startswith("why")' in candidate
    assert "from datetime import datetime" in candidate
    assert candidate.index("early_proxmox_backup_response = _hades_direct_proxmox_backup_read") < candidate.index(
        "early_compound_backup_response = _hades_direct_homelab_backup_compound"
    ) < candidate.index("early_owner_homelab_response = _hades_direct_homelab_read")
    assert output.stat().st_mode & 0o777 == 0o600
    assert active.read_text(encoding="utf-8") == ACTIVE

    # A production overlay may already contain the earlier placement/game
    # guards but lack broad owner/household reads. Upgrade that partial shape
    # without duplicating the existing guards.
    partial_route = '''
    if _hades_is_hermes_auxiliary_prompt(user_message):
        return "auxiliary"
    if _hades_service_placement_intent(user_message, getattr(self, "_hades_session_scope", "")):
        _hades_direct_homelab_read(user_message, getattr(self, "_hades_subject", ""), getattr(self, "_hades_session_scope", ""))
    if _hades_household_game_health_intent(user_message, getattr(self, "_hades_session_scope", "")):
        _hades_direct_homelab_read(user_message, getattr(self, "_hades_subject", ""), getattr(self, "_hades_session_scope", ""))
        _hades_logger.info("Household service-health boundary completed before staged automation routing")
    _hades_logger.info("Owner model-capacity follow-up failed closed without model invocation")
'''
    partial_active = directory / "partial-active.py"
    partial_active.write_text(
        ACTIVE.replace("    if _hades_household_game_health_intent(\n", partial_route + "    if _hades_household_game_health_intent(\n", 1),
        encoding="utf-8",
    )
    partial_candidate = directory / "partial-candidate.py"
    partial_result = run(
        "--active-overlay", str(partial_active), "--source", str(source), "--output", str(partial_candidate)
    )
    assert partial_result.returncode == 0, partial_result.stderr
    partial_text = partial_candidate.read_text(encoding="utf-8")
    assert partial_text.count("Owner direct homelab read completed before managed-server routing") == 1
    assert partial_text.count("Household direct homelab boundary completed before managed-server routing") == 1
    assert partial_text.count("Household service-health boundary completed before staged automation routing") == 1
    partial_recomposed = directory / "partial-recomposed.py"
    partial_second = run(
        "--active-overlay", str(partial_candidate), "--source", str(source), "--output", str(partial_recomposed)
    )
    assert partial_second.returncode == 0, partial_second.stderr
    assert partial_recomposed.stat().st_size == partial_candidate.stat().st_size

    recomposed = directory / "recomposed.py"
    second_composition = run(
        "--active-overlay", str(output), "--source", str(source), "--output", str(recomposed)
    )
    assert second_composition.returncode == 0, second_composition.stderr
    recomposed_text = recomposed.read_text(encoding="utf-8")
    assert recomposed_text.count(
        "Household service-health boundary completed before staged automation routing"
    ) == candidate.count(
        "Household service-health boundary completed before staged automation routing"
    )
    assert recomposed_text.count(
        "Household direct homelab read completed without model invocation"
    ) == candidate.count(
        "Household direct homelab read completed without model invocation"
    )
    assert recomposed.stat().st_size == output.stat().st_size

    # A second run must not overwrite an existing candidate.
    second = run("--active-overlay", str(active), "--source", str(source), "--output", str(output))
    assert second.returncode != 0
    assert "new path" in second.stderr

    # Unknown legacy call shapes fail without creating output.
    changed = directory / "changed.py"
    changed.write_text(ACTIVE.replace('_hades_direct_homelab_read(user_message)', '_hades_direct_homelab_read("changed")'), encoding="utf-8")
    refused = run("--active-overlay", str(changed), "--source", str(source), "--output", str(directory / "refused.py"))
    assert refused.returncode != 0
    assert "unrecognized active homelab" in refused.stderr
    assert not (directory / "refused.py").exists()

print("PASS synthetic focused overlay composition, permissions, preservation, idempotent refusal, and drift refusal")
