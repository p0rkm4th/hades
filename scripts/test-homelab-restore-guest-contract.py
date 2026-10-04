#!/usr/bin/env python3
"""Check bounded restore-task to current guest evidence and owner boundary."""
from __future__ import annotations

import ast
import re
from pathlib import Path


hermes_source = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
hermes_tree = ast.parse(hermes_source)
helper_names = {
    "_hades_backup_restore_guest_state_intent",
    "_hades_backup_restore_guest_state_response",
    "_hades_direct_backup_restore_guest_state_read",
    "_hades_homelab_guest_visibility_intent",
    "_hades_homelab_guest_inventory_intent",
    "_hades_homelab_guest_inventory_response",
    "_hades_direct_homelab_guest_inventory_read",
    "_hades_homelab_core_vm_placement_intent",
    "_hades_homelab_core_vm_placement_index_response",
    "_hades_homelab_core_vm_placement_response",
    "_hades_homelab_core_vm_placement_guest_index_response",
    "_hades_direct_homelab_core_vm_placement_read",
}
helpers = [
    node for node in hermes_tree.body
    if isinstance(node, ast.FunctionDef) and node.name in helper_names
]
assert {node.name for node in helpers} == helper_names


class Logger:
    def warning(self, *_args, **_kwargs):
        pass


dispatch_calls = []
activity = {
    "source_status": {"proxmox": "READABLE"},
    "endpoints": [{
        "source_id": "alpha", "status": "HEALTHY", "scope": "ALL_GUESTS",
        "truncated": False, "retrieved_at": "task-read-time",
        "events": [
            {"task_type": "qmrestore", "guest_id": "102", "status": "OK", "endtime": 100},
            {"task_type": "vzrestore", "guest_id": "203", "status": "ERROR", "endtime": 90},
            {"task_type": "qmrestore", "guest_id": "invalid/id", "status": "OK", "endtime": 80},
        ],
    }],
}
summary = {
    "proxmox_guest_inventory": {
        "status": "COMPLETE", "endpoints": [{
            "source_id": "alpha", "status": "COMPLETE",
            "visibility_status": "COMPLETE", "visibility_scope": "ALL_GUESTS",
            "retrieved_at": "guest-read-time", "truncated": False,
            "guests": [{
                "source_identity": "proxmox:alpha:qemu:102", "guest_type": "qemu",
                "guest_id": "102", "name": "Synthetic VM", "node": "Synthetic Node",
                "status": "RUNNING",
            }],
        }],
    },
}


def registry_read(tool_name, arguments=None):
    dispatch_calls.append((tool_name, arguments))
    return activity if tool_name == "homelab_recent_activity" else summary


namespace = {
    "re": re,
    "_hades_logger": Logger(),
    "_hades_direct_homelab_tool_result": registry_read,
}
exec(compile(ast.Module(body=helpers, type_ignores=[]), "sitecustomize.py", "exec"), namespace)
intent = namespace["_hades_backup_restore_guest_state_intent"]
response = namespace["_hades_backup_restore_guest_state_response"]
direct_read = namespace["_hades_direct_backup_restore_guest_state_read"]
guest_inventory_read = namespace["_hades_direct_homelab_guest_inventory_read"]
core_placement_read = namespace["_hades_direct_homelab_core_vm_placement_read"]
core_guest_index = namespace["_hades_homelab_core_vm_placement_guest_index_response"]

assert intent("Are the temporary guests from the backup restore still running?")
assert not intent("Restore the backup guest now")
assert direct_read("Are temporary restore guests still present?", "owner-1", "household") is None
answer = direct_read("Are temporary restore guests still present?", "owner-1", "owner")
assert "VM 102 is present and Proxmox currently reports it running" in answer, answer
assert "container 203 is absent from the current complete guest inventory" in answer, answer
assert "latest archived restore task is error" in answer, answer
assert "task-read-time" in answer and "guest-read-time" in answer, answer
assert "does not verify boot, operating-system, or application health" in answer, answer
assert dispatch_calls == [
    ("homelab_recent_activity", {"window_hours": 168}),
    ("homelab_summary", None),
], dispatch_calls
dispatch_calls.clear()
guest_answer = guest_inventory_read("What VMs are running?", "owner-1", "owner")
assert "Synthetic VM (VM 102) on Synthetic Node" in guest_answer, guest_answer
assert dispatch_calls == [("homelab_summary", None)], dispatch_calls
dispatch_calls.clear()
assert "only in an owner session" in guest_inventory_read(
    "What VMs are running?", "household-1", "household"
)
assert not dispatch_calls, dispatch_calls
dispatch_calls.clear()
summary["proxmox_guest_inventory"]["endpoints"][0]["guests"].append({
    "source_identity": "proxmox:alpha:qemu:202", "guest_type": "qemu",
    "guest_id": "202", "name": "HADES Core", "node": "Synthetic Hypervisor",
    "status": "RUNNING",
})
core_answer = core_placement_read("Where is HADES Core running?", "owner-1", "owner")
assert "HADES Core (VM 202) is running on Synthetic Hypervisor" in core_answer, core_answer
assert dispatch_calls == [("homelab_summary", None)], dispatch_calls
dispatch_calls.clear()
complete_core_index = {"proxmox_guest_inventory": {
    "status": "COMPLETE", "endpoints": [{
        "source_id": "pve-alpha", "status": "COMPLETE",
        "visibility_scope": "ALL_GUESTS", "truncated": False,
        "retrieved_at": "current-guest-index-time", "guests": [
            {"name": "hades-core", "guest_type": "qemu", "guest_id": "200",
             "node": "Synthetic Hypervisor", "status": "STOPPED"},
            {"name": "hades-core", "guest_type": "qemu", "guest_id": "202",
             "node": "Synthetic Hypervisor", "status": "RUNNING"},
        ],
    }],
}}
index_answer = core_guest_index("Where is HADES running?", complete_core_index)
assert "hades-core (VM 200) is stopped" in index_answer, index_answer
assert "hades-core (VM 202) is running" in index_answer, index_answer
assert "current-guest-index-time" in index_answer, index_answer
assert core_guest_index("What's running?", complete_core_index) is None
assert core_guest_index("Where is HADES running?", {"resources": [
    {"name": "hades-core", "runtime_status": "running"},
]}) is None, "incumbent adapters without a guest index must retain their legacy route"
assert core_placement_read("Where is HADES Core running?", "household-1", "household") is None
assert not dispatch_calls, dispatch_calls

partial_summary = {"proxmox_guest_inventory": {"status": "PARTIAL", "endpoints": [{
    "source_id": "alpha", "status": "PARTIAL", "visibility_status": "PARTIAL",
    "visibility_scope": "SELECTED_GUESTS", "truncated": False, "guests": [],
}]}}
partial_answer = response(activity, partial_summary)
assert "can't tell whether container 203 remains" in partial_answer, partial_answer

incomplete_history = {
    "source_status": {"proxmox": "PARTIAL"},
    "endpoints": [{
        "source_id": "alpha", "status": "PARTIAL", "scope": "SELECTED_GUESTS",
        "truncated": True, "events": [],
    }],
}
unknown_answer = response(incomplete_history, summary)
assert "partial, truncated, or not fully visible" in unknown_answer, unknown_answer

# The routed path executes before the generic direct homelab handler, whose
# write-word guard deliberately declines restore requests.
agent_method = next(
    node for node in ast.walk(hermes_tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
)
restore_calls = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_backup_restore_guest_state_read"
]
inventory_calls = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_guest_inventory_read"
]
core_calls = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_core_vm_placement_read"
]
generic_calls = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_read"
]
assert (
    restore_calls and inventory_calls and core_calls and generic_calls
    and min(restore_calls) < max(generic_calls)
    and min(inventory_calls) < max(generic_calls)
    and min(core_calls) < max(generic_calls)
), (restore_calls, inventory_calls, core_calls, generic_calls)
backup_route = next(
    node for node in hermes_tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase2_backup_response"
)
backup_restore_guard = [
    node.lineno for node in ast.walk(backup_route)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_backup_restore_guest_state_intent"
]
assert backup_restore_guard, "restore-state reads must not enter Backup Check lifecycle handling"
print("PASS owner guest listing, Core placement, and restore checks use bounded, completeness-qualified Proxmox evidence")
