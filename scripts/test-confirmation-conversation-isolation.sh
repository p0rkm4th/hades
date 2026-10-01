#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import ast
import hashlib
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

source_path = Path(os.environ.get("HADES_CONFIRMATION_OVERLAY_SOURCE", "hermes/sitecustomize.py"))
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source)
provision_preview = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_pending_provision_preview"
)
preview_bound_fields = {
    node.slice.value
    for node in ast.walk(provision_preview)
    if isinstance(node, ast.Subscript)
    and isinstance(node.value, ast.Name)
    and node.value.id == "pending"
    and isinstance(node.ctx, ast.Store)
    and isinstance(node.slice, ast.Constant)
}
assert {"operation", "target", "resources", "previewed"} <= preview_bound_fields, (
    "provision preview does not persist its exact operation, placement, resource limits, and preview state"
)
assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == "pending_put"
    and any(isinstance(arg, ast.Name) and arg.id == "pending" for arg in node.args)
    for node in ast.walk(provision_preview)
), "provision preview is not durably stored before asking for confirmation"
confirmation_branch = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.If)
    and isinstance(node.test, ast.Name)
    and node.test.id == "_explicit_provision_confirmation"
)
confirmation_text = ast.unparse(confirmation_branch)
for requirement in (
    "_pending.get('operation') != 'provision_guest'",
    "_spec != _expected_plan[1]",
    "_target['node'] not in _nodes",
    "_control_module.provision_guest(_template, _target",
    "_provision_write_started = True",
    "'OUTCOME_UNKNOWN' if _provision_write_started else 'FAILED'",
):
    assert requirement in confirmation_text, (
        f"provision confirmation is not bound to required material parameters: {requirement}"
    )
function = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_turn_identity"
)
namespace = {"hashlib": hashlib}
exec(compile(ast.Module(body=[function], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
identity = namespace["_hades_turn_identity"]
from integrations.automation import LifecycleStore
from integrations.automation.phase3_self_service import (
    Phase3Authority, Phase3Catalog, Phase3Service, Phase3Store,
)

history = [{"role": "user", "content": "verify the backups"}]

first_chat = identity("yes", history, "openwebui-chat-alpha")
second_chat = identity("yes", history, "openwebui-chat-beta")
assert first_chat != second_chat, "separate chats shared a confirmation key"
assert identity("yes", [], "openwebui-chat-alpha") == first_chat, "worker recovery changed a conversation key"
assert identity("yes", history) == "", "a transcript was accepted as confirmation identity without a server conversation ID"

identity_calls = [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_turn_identity"
]
phase2_identity_calls = [
    call for call in identity_calls
    if not (call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "")
]
assert len(phase2_identity_calls) == 3, "a Phase 2 confirmation path stopped using the shared identity helper"
assert all(
    len(call.args) == 3
    and isinstance(call.args[2], ast.Call)
    and isinstance(call.args[2].func, ast.Name)
    and call.args[2].func.id == "getattr"
    and isinstance(call.args[2].args[1], ast.Constant)
    and call.args[2].args[1].value == "_hades_conversation_id"
    for call in phase2_identity_calls
), "a Phase 2 confirmation path is not keyed by the API conversation ID"
assert 'self._hades_conversation_id = str(kwargs.get("session_id") or "").strip()' in source
assert "_early_candidates" not in source, "typed confirmations still recover actor-wide in the early dispatcher"
provision_keys = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_pending_provision_keys"
)
provision_namespace = {"_hades_turn_identity": identity}
exec(compile(ast.Module(body=[provision_keys], type_ignores=[]), "sitecustomize.py", "exec"), provision_namespace)
agent_alpha = type("Agent", (), {"_hades_subject": "synthetic-owner", "session_id": "chat-alpha", "_hades_gateway_session_key": "same-user-key"})()
agent_beta = type("Agent", (), {"_hades_subject": "synthetic-owner", "session_id": "chat-beta", "_hades_gateway_session_key": "same-user-key"})()
agent_without_chat = type("Agent", (), {"_hades_subject": "synthetic-owner", "session_id": "", "_hades_gateway_session_key": "same-user-key"})()
assert provision_namespace["_hades_pending_provision_keys"](agent_alpha) != provision_namespace["_hades_pending_provision_keys"](agent_beta)
assert provision_namespace["_hades_pending_provision_keys"](agent_without_chat) == []
assert 'str(kwargs.get("session_id") or "").strip()' in source
assert 'or _agent_first_user' not in source, "agent construction still substitutes transcript text for a server chat ID"

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "pending.sqlite")
    owner = "synthetic-owner"
    first_key = f"session:{owner}:{first_chat}"
    second_key = f"session:{owner}:{second_chat}"
    writer = LifecycleStore(path)
    writer.pending_put(first_key, owner, {"template_id": "backup", "action": "run"}, 4_000_000_000)
    writer.pending_put(second_key, owner, {"template_id": "inventory", "action": "pause"}, 4_000_000_000)
    recovery_worker = LifecycleStore(path)
    assert recovery_worker.pending_get(first_key, owner)["action"] == "run"
    assert recovery_worker.pending_get(second_key, owner)["action"] == "pause"

    provision_key = f"session:{owner}:{identity('create it', history, 'openwebui-minecraft-chat')}"
    recovery_worker.pending_put(
        provision_key, owner,
        {"template_id": "hades-self-service-provision", "previewed": True},
        4_000_000_000,
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        provision_claims = list(pool.map(
            lambda _index: LifecycleStore(path).pending_take(provision_key, owner),
            range(8),
        ))
    assert sum(value is not None for value in provision_claims) == 1, provision_claims
    assert recovery_worker.pending_get(provision_key, owner) is None

    # A stale Backup Verification preview in chat A must not be consumed by a
    # bare confirmation arriving from a distinct Open WebUI chat B.
    backup_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase2_backup_response"
    )
    pending_record_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_hades_pending_record_is_current"
    )
    backup_namespace = {
        "os": os,
        "re": __import__("re"),
        "time": time,
        "_hades_logger": logging.getLogger("backup-confirmation-test"),
        "_HADES_PENDING_PHASE2": {},
        "_hades_health_watch_state_path": lambda: path,
    }
    exec(compile(ast.Module(body=[pending_record_function, backup_function], type_ignores=[]), "sitecustomize.py", "exec"), backup_namespace)
    recovery_worker.pending_put(
        f"session:{owner}:{first_chat}", owner,
        {"template_id": "hades-backup-verification", "action": "run"},
        4_000_000_000,
    )
    third_chat = identity("yes", history, "openwebui-chat-gamma")
    mismatch = backup_namespace["_hades_phase2_backup_response"]("yes", owner, "owner", third_chat)
    assert mismatch and "couldn't match that confirmation" in mismatch.lower(), (mismatch, recovery_worker.pending_for_actor(owner))

    # A negative response cancels only an uncompleted Backup Check action
    # belonging to this actor and this exact server conversation.
    recovery_worker.pending_put(
        f"session:{owner}:{first_chat}", owner,
        {"template_id": "hades-backup-verification", "action": "run"},
        4_000_000_000,
    )
    declined = backup_namespace["_hades_phase2_backup_response"]("no", owner, "owner", first_chat)
    assert declined and "nothing was changed" in declined.casefold(), declined
    assert recovery_worker.pending_get(f"session:{owner}:{first_chat}", owner) is None

    recovery_worker.pending_put(
        f"session:{owner}:{first_chat}", owner,
        {"template_id": "hades-backup-verification", "action": "run"},
        4_000_000_000,
    )
    other_chat_no = backup_namespace["_hades_phase2_backup_response"]("no", owner, "owner", second_chat)
    assert other_chat_no is None
    assert recovery_worker.pending_get(f"session:{owner}:{first_chat}", owner) is not None
    explicit_decline = backup_namespace["_hades_phase2_backup_response"](
        "No, don't run the backup check.", owner, "owner", first_chat
    )
    assert explicit_decline and "nothing was changed" in explicit_decline.casefold(), explicit_decline
    assert recovery_worker.pending_get(f"session:{owner}:{first_chat}", owner) is None

    # Phase 3 lifecycle controls also require the exact conversation key.
    phase3_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase3_response"
    )
    phase3_path = str(Path(root) / "phase3.sqlite")
    phase3_actor = Phase3Authority(owner, "household", frozenset({"grocy.household"}))
    phase3_owner_actor = Phase3Authority(owner, "owner", frozenset({"grocy.household", "backup.evidence"}))
    phase3_service = Phase3Service(Phase3Store(phase3_path), catalog=Phase3Catalog())
    phase3_preview = phase3_service.preview(phase3_actor, "low-inventory-summary", {})
    phase3_record = phase3_service.confirm(
        phase3_actor, phase3_preview["preview_id"], phase3_preview["preview_hash"], "phase3-create"
    )
    phase3_namespace = {
        "os": os,
        "re": __import__("re"),
        "time": time,
        "secrets": __import__("secrets"),
        "_hades_phase3_enabled": lambda: True,
        "_hades_phase3_authority": lambda _subject, requested_scope: phase3_owner_actor if requested_scope == "owner" else phase3_actor,
        "_hades_phase3_service": lambda: phase3_service,
    }
    exec(compile(ast.Module(body=[phase3_function], type_ignores=[]), "sitecustomize.py", "exec"), phase3_namespace)
    phase3_pending = f"session:{owner}:{first_chat}"
    phase3_service.store.pending_put(
        phase3_pending, owner,
        {"kind": "action", "action": "pause", "automation_id": phase3_record["automation_id"]},
    )
    cross_chat_phase3 = phase3_namespace["_hades_phase3_response"]("yes", owner, "household", third_chat)
    assert "couldn't match that confirmation" in cross_chat_phase3.lower()
    assert phase3_service.store.get(phase3_record["automation_id"])["enabled"] is True
    same_chat_phase3 = phase3_namespace["_hades_phase3_response"]("yes", owner, "household", first_chat)
    assert "paused" in same_chat_phase3.lower()
    assert phase3_service.store.get(phase3_record["automation_id"])["enabled"] is False
    phase3_service.store.pending_put(
        f"session:{owner}:{first_chat}", owner,
        {"kind": "admin-disable", "automation_id": "synthetic-automation"},
    )
    cross_chat_owner = phase3_namespace["_hades_phase3_response"]("yes", owner, "owner", third_chat)
    assert "couldn't match that confirmation" in cross_chat_owner.lower()
    assert phase3_service.store.pending_get(f"session:{owner}:{first_chat}", owner) is not None
    missing_chat_owner = phase3_namespace["_hades_phase3_response"](
        "stop low-inventory-summary", owner, "owner", ""
    )
    assert "couldn't securely tie" in missing_chat_owner.lower()
    missing_chat_phase3 = phase3_namespace["_hades_phase3_response"]("resume my weekly summary", owner, "household", "")
    assert "couldn't securely tie" in missing_chat_phase3.lower()
    assert phase3_service.store.get(phase3_record["automation_id"])["enabled"] is False
print("PASS typed confirmations bind to server conversation IDs and remain recoverable across workers")
print("PASS provisioning confirmations bind to the exact preview operation, target, resources, and write lifecycle")
PY
