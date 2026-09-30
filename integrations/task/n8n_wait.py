"""Fixed n8n wait graph for the Alpha Task coordination lane.

This is intentionally a typed adapter, not a user-supplied workflow builder.
The graph only accepts a task-owned resume timestamp and carries no arbitrary
HTTP, shell, credential, or domain mutation nodes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping


def wait_workflow_id(task_id: str) -> str:
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:20]
    return f"hades-task-wait-{digest}"


def build_wait_workflow(task_id: str, resume_at: str) -> Mapping[str, Any]:
    """Build the only n8n graph Alpha Tasks may create."""
    if not task_id.strip() or not resume_at.strip():
        raise ValueError("task and resume timestamp are required")
    try:
        datetime.fromisoformat(resume_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError("resume timestamp must be ISO-8601") from exc
    workflow_id = wait_workflow_id(task_id)
    webhook_path = workflow_id
    return {
        "id": workflow_id,
        "name": "HADES bounded Task wait",
        "active": False,
        "settings": {"executionOrder": "v1", "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all"},
        "nodes": [
            {
                "parameters": {"httpMethod": "POST", "path": webhook_path, "responseMode": "onReceived", "options": {}},
                "id": "task-wait-trigger",
                "name": "HADES Task wake request",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [240, 240],
                "webhookId": webhook_path,
            },
            {
                "parameters": {"resume": "specificTime", "dateTime": resume_at},
                "id": "task-wait",
                "name": "HADES Task scheduled wait",
                "type": "n8n-nodes-base.wait",
                "typeVersion": 1.1,
                "position": [520, 240],
            },
        ],
        "connections": {
            "HADES Task wake request": {"main": [[{"node": "HADES Task scheduled wait", "type": "main", "index": 0}]]},
            "HADES Task scheduled wait": {"main": [[]]},
        },
        "tags": [{"name": "hades-template:task-wait"}, {"name": "hades-approved:true"}],
    }


def fixed_wait_contract(workflow: Mapping[str, Any]) -> bool:
    """Reject any graph that is not the exact bounded wait shape."""
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list) or {node.get("type") for node in nodes if isinstance(node, Mapping)} != {
        "n8n-nodes-base.webhook", "n8n-nodes-base.wait"
    }:
        return False
    return all(
        isinstance(node, Mapping)
        and node.get("type") in {"n8n-nodes-base.webhook", "n8n-nodes-base.wait"}
        and not node.get("credentials")
        for node in nodes
    )
