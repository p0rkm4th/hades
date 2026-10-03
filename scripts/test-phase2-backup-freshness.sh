#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import ast
import hashlib
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from integrations.automation import (
    BackupObservation,
    BackupVerificationService,
    BackupVerificationSpec,
    LifecycleStore,
)

source = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase2_backup_freshness_response"
)
intent_helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_is_backup_freshness_intent"
)
model_fit_helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_homelab_explicit_model_fit_intent"
)
aux_guard = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "_HADES_HERMES_AUXILIARY_PROMPT" for target in node.targets)
)
aux_helper = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_is_hermes_auxiliary_prompt"
)
conversation = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
)
route = source.index("_hades_phase2_backup_freshness_response(", source.index("def _hades_run_conversation"))
phase3_route = source.index("# Recent Phase 3 results are read", route)
assert route < phase3_route, "Phase 3 result history can intercept Phase 2 backup freshness"
assert "if not records:\n            return proxmox_evidence()" in ast.get_source_segment(source, helper)
assert r"when\s+did\s+" in source[source.index("# Recent Phase 3 results are read"):], "outer result-route prefilter blocks ordinary last-check wording"

with tempfile.TemporaryDirectory() as root:
    state = str(Path(root) / "state.sqlite")
    actor = "synthetic-alpha"
    store = LifecycleStore(state)
    result = {"automation_id": "synthetic-backup", "production_schedule": True}
    payload = {"target_id": "hades-repository", "shared_subjects": []}
    store.put("backup-op", actor, "hades-backup-verification", payload, "PROMOTED", result)
    service = BackupVerificationService(state, BackupVerificationSpec("synthetic-backup", actor))
    service.observe([BackupObservation("hades-repository", "HEALTHY", "safe fixture", "2026-09-25T12:34:00+00:00")])
    db_before = hashlib.sha256(Path(state).read_bytes()).hexdigest()

    namespace = {
        "_HADES_HERMES_AUXILIARY_PROMPT": None,
        "re": re,
        "os": os,
        "time": time,
        "_hades_logger": logging.getLogger("backup-freshness-test"),
        "Path": Path,
        # The handler's early privacy gate is exercised in its dedicated
        # contract; keep this route test focused on backup freshness dispatch.
        "_hades_explicit_private_research_request": lambda _text: False,
        "_hades_private_person_fallback_suspected": lambda _text: False,
        "_HADES_PRIVATE_RESEARCH_FOLLOWUP": re.compile(r"(?!)"),
        "_hades_health_watch_state_path": lambda: state,
        "_hades_phase2_resource_shares": lambda _subject: set(),
        "_hades_direct_proxmox_backup_read": lambda text, *_args, **_kwargs: (
            "PROXMOX VZDUMP: synthetic current evidence."
            if text in {"When were our backups last verified?", "When did we last check the backups?", "Are my backups current?"}
            else None
        ),
    }
    exec(compile(ast.Module(body=[aux_guard, aux_helper, intent_helper, helper, model_fit_helper], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
    intent = namespace["_hades_is_backup_freshness_intent"]
    assert intent("Do we have a recent backup?")
    assert intent("Was our backup checked recently?")
    assert intent("Are the backups current?")
    assert intent("When did we last check the backups?")
    assert not intent("Run the Backup Check now")
    assert not intent("Check backups now")
    freshness = namespace["_hades_phase2_backup_freshness_response"]
    assert freshness("Are my Proxmox backups current?", actor, "owner") is None
    assert freshness("Are the server backups up to date?", actor, "owner") is None
    answer = freshness("When were our backups last verified?", actor, "owner")
    assert "HADES repository backup: healthy" in answer, answer
    assert "PROXMOX VZDUMP: synthetic current evidence." in answer, answer
    assert "do not verify host, VM, service, or household-data backups" in answer, answer
    assert "last successful check 2026-09-25 12:34 UTC" in answer, answer
    natural_answer = freshness("When did we last check the backups?", actor, "owner")
    assert "HADES repository backup: healthy" in natural_answer, natural_answer
    assert "PROXMOX VZDUMP: synthetic current evidence." in natural_answer, natural_answer
    repository_only = freshness("Is my HADES repository backup current?", actor, "owner")
    assert "HADES repository backup: healthy" in repository_only, repository_only
    assert "PROXMOX VZDUMP" not in repository_only, repository_only
    assert "independent off-site custody" in natural_answer, natural_answer
    exec(compile(ast.Module(body=[conversation], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
    fake_agent_type = type("Agent", (), {
        "_hades_subject": actor,
        "_hades_session_scope": "owner",
        "stream_delta_callback": None,
        "model": "test-model",
    })
    namespace["_AIAgent"] = type("OriginalAgent", (), {
        "run_conversation": staticmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fallback route ran")))
    })
    dispatch = namespace["_hades_run_conversation"](
        fake_agent_type(), "When did we last check the backups?"
    )
    assert "HADES repository backup: healthy" in dispatch["final_response"], dispatch
    assert "shall I run" not in dispatch["final_response"].casefold(), dispatch
    assert dispatch["api_calls"] == 0 and dispatch["completed"] is True, dispatch
    assert hashlib.sha256(Path(state).read_bytes()).hexdigest() == db_before, "freshness conversation route wrote pending/action state"
    assert freshness("How old are the backups?", "synthetic-beta", "household") is None
    assert "couldn't verify" in freshness("Are my backups up to date?", actor, "unknown")
    assert freshness("Show backup setup", actor, "owner") is None
    assert hashlib.sha256(Path(state).read_bytes()).hexdigest() == db_before, "freshness lookup modified canonical lifecycle state"
    namespace["_hades_health_watch_state_path"] = lambda: str(Path(root) / "not-configured.sqlite")
    assert freshness("Are my backups current?", actor, "owner") == "PROXMOX VZDUMP: synthetic current evidence."
    assert freshness("Are my backups up to date?", actor, "owner") is None

    household_state = str(Path(root) / "shared.sqlite")
    shared = LifecycleStore(household_state)
    shared.put("shared-op", actor, "hades-backup-verification",
               {"target_id": "hades-repository", "shared_subjects": ["synthetic-beta"]},
               "PROMOTED", result)
    BackupVerificationService(household_state, BackupVerificationSpec("synthetic-backup", actor)).observe(
        [BackupObservation("hades-repository", "STALE", "safe fixture", "2026-09-25T12:34:00+00:00")]
    )
    namespace["_hades_health_watch_state_path"] = lambda: household_state
    namespace["_hades_phase2_resource_shares"] = lambda _subject: {"backup.evidence"}
    shared_answer = freshness("Are our backups up to date?", "synthetic-beta", "household")
    assert "stale and needs attention" in shared_answer, shared_answer
print("PASS Phase 2 visible backup freshness takes precedence and stays requester scoped")
PY
