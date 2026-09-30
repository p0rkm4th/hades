#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'rm -rf "$tmp_root"' EXIT

python - "$repo_root" "$tmp_root/tasks.sqlite" <<'PY'
import ast
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

repo_root = Path(sys.argv[1])
sys.path.insert(0, str(repo_root))

from integrations.task import TaskStatus, TaskStore

source = (repo_root / "hermes" / "sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
task_route = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_task_response"
)
notification_route = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_task_notification_feed"
)
os.environ["HADES_TASK_STATE_FILE"] = sys.argv[2]
namespace = {"re": re, "hashlib": hashlib, "time": time, "json": json, "os": os, "Path": Path}
exec(compile(ast.Module(body=[notification_route, task_route], type_ignores=[]), "sitecustomize.py", "exec"), namespace)

store = TaskStore(sys.argv[2])
owner = "synthetic-owner-subject"
other = "synthetic-other-subject"
no_tasks_subject = "synthetic-no-tasks-subject"
completed = store.create(
    task_id="task-owner-completed001", actor_subject_id=owner,
    goal="Review pantry before Friday", status=TaskStatus.COMPLETED,
)
active_one = store.create(
    task_id="task-owner-active001", actor_subject_id=owner,
    goal="Check pantry for dinner", status=TaskStatus.WAITING,
)
active_two = store.create(
    task_id="task-owner-active002", actor_subject_id=owner,
    goal="Review weekend plan", status=TaskStatus.AWAITING_APPROVAL,
)
blocked = store.create(
    task_id="task-owner-blocked001", actor_subject_id=owner,
    goal="Check backup status", status=TaskStatus.BLOCKED,
)
uncertain = store.create(
    task_id="task-owner-uncertain001", actor_subject_id=owner,
    goal="Verify dinner plan", status=TaskStatus.OUTCOME_UNKNOWN,
)
failed = store.create(
    task_id="task-owner-failed001", actor_subject_id=owner,
    goal="Review the grocery delivery", status=TaskStatus.FAILED,
)
resumable = store.create(
    task_id="task-owner-resume001", actor_subject_id=owner,
    goal="Check shared pantry", status=TaskStatus.WAITING,
)
other_task = store.create(
    task_id="task-other-private001", actor_subject_id=other,
    goal="Private other-account task", status=TaskStatus.FAILED,
)
namespace["_hades_task_store"] = lambda: store
namespace["_hades_task_remove_wait"] = lambda *_args: True
namespace["_hades_task_grocy_snapshot"] = lambda: {
    "source": "Grocy", "endpoint": "/api/stock", "observed_at": 1,
    "item_count": 0, "items": [],
}
namespace["_hades_logger"] = type("Logger", (), {"warning": lambda *_args: None})()
route = namespace["_hades_task_response"]
notification_feed = namespace["_hades_task_notification_feed"]

with open(sys.argv[2], 'rb') as handle:
    notification_store_before = hashlib.sha256(handle.read()).hexdigest()
owner_feed = json.loads(notification_feed("HADES_TASK_NOTIFICATION_FEED_V1", owner, "owner"))
other_feed = json.loads(notification_feed("HADES_TASK_NOTIFICATION_FEED_V1", other, "household"))
assert owner_feed["version"] == 1
assert {item["task_id"] for item in owner_feed["tasks"]} == {
    active_two["task_id"], blocked["task_id"], uncertain["task_id"], failed["task_id"], completed["task_id"]
}
assert all(item["revision"] == 1 for item in owner_feed["tasks"])
assert [item["task_id"] for item in other_feed["tasks"]] == [other_task["task_id"]]
assert json.loads(notification_feed("HADES_TASK_NOTIFICATION_FEED_V1", "", ""))["error"] == "identity_unavailable"
assert notification_feed("ordinary user text", owner, "owner") is None
with open(sys.argv[2], 'rb') as handle:
    assert hashlib.sha256(handle.read()).hexdigest() == notification_store_before
missing_store = str(Path(sys.argv[2]).with_name("missing-notifications.sqlite"))
os.environ["HADES_TASK_STATE_FILE"] = missing_store
assert json.loads(notification_feed("HADES_TASK_NOTIFICATION_FEED_V1", owner, "owner"))["tasks"] == []
assert not Path(missing_store).exists(), "read-only notification polling created Task state"
os.environ["HADES_TASK_STATE_FILE"] = sys.argv[2]

recent = route("list my tasks", owner, "owner", [])
assert completed["goal"] in recent and active_one["goal"] in recent
assert active_two["goal"] in recent and other_task["goal"] not in recent, recent
assert all(task["task_id"] not in recent for task in (completed, active_one, active_two, other_task)), recent
completed_history = route("show my task history", owner, "owner", [])
assert completed["goal"] in completed_history and completed["task_id"] not in completed_history

attention = route("What needs my attention?", owner, "owner", [])
assert "Review weekend plan is waiting for your approval." in attention, attention
assert "Check backup status is blocked" in attention, attention
assert "result for Verify dinner plan is uncertain" in attention, attention
assert "couldn't finish Review the grocery delivery" in attention, attention
assert "task-owner-" not in attention and "Private other-account task" not in attention
assert "no tasks needing your attention" in route("Anything I need to do?", no_tasks_subject, "household", []).lower(), route("Anything I need to do?", no_tasks_subject, "household", [])
assert all(store.get(task["task_id"], owner)["task_revision"] == task["task_revision"] for task in (active_two, blocked, uncertain, failed))

namespace["_hades_task_store"] = lambda: (_ for _ in ()).throw(OSError("synthetic Task store outage"))
for prompt, actor, actor_scope in (
    ("What needs my attention?", owner, "owner"),
    ("Anything I need to do?", other, "household"),
):
    unavailable = route(prompt, actor, actor_scope, [])
    assert unavailable == "I can't check your task updates right now. Please try again shortly.", unavailable
assert route("Tell me a joke", owner, "owner", []) is None, "unrelated prompts must keep existing routing"
namespace["_hades_task_store"] = lambda: store

completed_only = route("show completed tasks", owner, "owner", [])
assert completed["goal"] in completed_only
assert completed["task_id"] not in completed_only and active_one["task_id"] not in completed_only

selected = route(
    f"show task {completed['task_id']}", owner, "owner", []
)
assert "status: completed" in selected.lower() and completed["goal"] in selected
assert completed["task_id"] not in selected, selected

friendly_review = route(
    f"Show me the status of my task: {active_two['goal']}", owner, "owner", []
)
assert "Review weekend plan" in friendly_review and "awaiting approval" in friendly_review, friendly_review
assert active_two["task_id"] not in friendly_review, friendly_review
foreign_name = route(
    f"Show me the status of my task: {other_task['goal']}", owner, "owner", []
)
assert "couldn't find a task with that name for this account" in foreign_name.lower(), repr(foreign_name)
assert other_task["goal"] not in foreign_name and other_task["task_id"] not in foreign_name

unowned = route(
    f"show task {other_task['task_id']}", owner, "owner", []
)
assert "couldn't find that task for this account" in unowned.lower()
assert other_task["task_id"] not in unowned

approval = route(f"approve task {resumable['task_id']}", owner, "owner", [])
assert "approval is required" in approval.lower()
approved = route(f"approve task {resumable['task_id']}", owner, "owner", [])
assert "approved the current task revision" in approved.lower()
continued = route(f"continue task {resumable['task_id']}", owner, "owner", [])
assert "completed the bounded task" in continued.lower()
assert store.get(resumable["task_id"], owner)["status"] == TaskStatus.COMPLETED.value

ambiguous = route("cancel task", owner, "owner", [])
assert "which task should i cancel" in ambiguous.lower()
assert store.get(active_one["task_id"], owner)["status"] == TaskStatus.WAITING.value
wrong_topic = route("cancel the Friday task", owner, "owner", [])
assert "which task should i cancel" in wrong_topic.lower()
assert store.get(active_one["task_id"], owner)["status"] == TaskStatus.WAITING.value

cancelled = route(
    f"cancel task {active_one['task_id']}", owner, "owner", []
)
assert "cancelled the task" in cancelled.lower()
assert store.get(active_one["task_id"], owner)["status"] == TaskStatus.CANCELLED.value
print("PASS task chat history, explicit verbs, actor isolation, and cancellation clarification")
PY
