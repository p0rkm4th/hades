#!/usr/bin/env bash
set -euo pipefail

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python - "$tmp" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from integrations.task import (
    ApprovalError,
    AuthorityError,
    ConcurrencyError,
    TaskStatus,
    TaskStore,
    build_wait_workflow,
    fixed_wait_contract,
)

root = Path(sys.argv[1])
assert fixed_wait_contract(build_wait_workflow("task-alpha", "2026-09-25T08:00:00Z"))
assert not fixed_wait_contract({"nodes": [{"type": "n8n-nodes-base.executeCommand"}]})
store = TaskStore(root / "tasks.sqlite")
actor = "owner-subject"
task = store.create(
    task_id="task-spaghetti-alpha",
    actor_subject_id=actor,
    goal="Help me get ready to make spaghetti Friday",
    resource_scope={"grocy": "grocy.household"},
    required_authority={"read": ["grocy.household"], "write": ["grocy.household"]},
    bounded_plan=[{"step": "read_recipe"}, {"step": "read_stock"}, {"step": "wait_until", "day": "Friday"}],
)
assert task["status"] == TaskStatus.PROPOSED.value and task["task_revision"] == 1
task = store.transition(task["task_id"], actor, 1, TaskStatus.WAITING,
                        fields={"current_step": "wait_until", "waiting_reason": "Friday", "next_eligible_action": "scheduled_wake"})
assert task["status"] == TaskStatus.WAITING.value
task = store.replan(task["task_id"], actor, 2, goal="Help me get ready to make lasagna Saturday",
                    bounded_plan=[{"step": "read_recipe", "recipe": "lasagna"}], current_step="read_recipe")
assert task["status"] == TaskStatus.READY.value and task["approval_state"] == {}
task = store.request_approval(task["task_id"], actor, 3, action="add_to_grocery_list",
                              resource={"system": "grocy", "resource_id": "grocy.household"},
                              parameters={"items": ["tomato sauce"]})
assert task["status"] == TaskStatus.AWAITING_APPROVAL.value
try:
    store.approve(task["task_id"], actor, 4, action="remove_from_grocery_list",
                  resource={"system": "grocy", "resource_id": "grocy.household"}, parameters={"items": ["tomato sauce"]},
                  authority_checker=lambda *_: True)
except ApprovalError:
    pass
else:
    raise AssertionError("materially changed approval was accepted")
task = store.approve(task["task_id"], actor, 4, action="add_to_grocery_list",
                     resource={"system": "grocy", "resource_id": "grocy.household"},
                     parameters={"items": ["tomato sauce"]}, authority_checker=lambda *_: True)
assert task["status"] == TaskStatus.READY.value
task = store.begin_execution(task["task_id"], actor, 5, execution_id="exec-1", step_id="add",
                             executor="mcp", idempotency_key="task-spaghetti-alpha:add:v1",
                             action="add_to_grocery_list", resource={"system": "grocy", "resource_id": "grocy.household"},
                             authority_checker=lambda *_: True)
assert task["status"] == TaskStatus.RUNNING.value
same = store.begin_execution(task["task_id"], actor, 6, execution_id="exec-duplicate", step_id="add",
                             executor="mcp", idempotency_key="task-spaghetti-alpha:add:v1",
                             action="add_to_grocery_list", resource={"system": "grocy", "resource_id": "grocy.household"},
                             authority_checker=lambda *_: True)
assert same["status"] == TaskStatus.RUNNING.value
task = store.record_execution(task["task_id"], actor, 6, execution_id="exec-1", status="OUTCOME_UNKNOWN")
assert task["status"] == TaskStatus.OUTCOME_UNKNOWN.value
task = store.reconcile_unknown(task["task_id"], actor, 7, execution_id="exec-1", succeeded=True,
                               canonical_refs={"grocy_product_id": 99})
assert task["status"] == TaskStatus.COMPLETED.value
waiting = store.create(
    task_id="task-waiting-read",
    actor_subject_id=actor,
    goal="Read pantry then wait",
    resource_scope={"systems": ["grocy.household", "n8n.wait"]},
    required_authority={"read": ["grocy.household"], "write": []},
    bounded_plan=[{"step": "read_shared_pantry"}, {"step": "wait_until"}],
)
waiting = store.transition(waiting["task_id"], actor, 1, TaskStatus.READY,
                           fields={"current_step": "read_shared_pantry", "next_eligible_action": "execute"})
waiting = store.begin_execution(waiting["task_id"], actor, 2, execution_id="exec-read", step_id="read_shared_pantry",
                                executor="grocy", idempotency_key="task-waiting-read:read:v1", action="read",
                                resource={"system": "grocy.household"})
waiting = store.record_execution(waiting["task_id"], actor, 3, execution_id="exec-read", status="SUCCEEDED",
                                 canonical_refs={"grocy_endpoint": "/api/stock"},
                                 success_status=TaskStatus.WAITING, next_eligible_action="scheduled_wake")
assert waiting["status"] == TaskStatus.WAITING.value
assert len(store.events(task["task_id"], actor)) >= 8
try:
    store.get(task["task_id"], "household-a")
except Exception:
    pass
else:
    raise AssertionError("private task leaked across actors")
backup = store.backup(root / "backup.sqlite")
restored = TaskStore.restore(backup, root / "restored.sqlite")
assert TaskStore(restored).get(task["task_id"], actor)["status"] == TaskStatus.COMPLETED.value
print("PASS Task store lifecycle, revision-bound approval, idempotency, unknown reconciliation, isolation, backup, restore")
PY
