#!/usr/bin/env bash
set -euo pipefail

: "${N8N_BASE_URL:?set N8N_BASE_URL to the private n8n API base URL}"
: "${N8N_API_KEY:?set N8N_API_KEY in the calling environment; it is never printed}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHONPATH="$repo_dir" python3 - <<'PY'
import os

from integrations.automation import N8NHttpGateway

gateway = N8NHttpGateway(os.environ["N8N_BASE_URL"], os.environ["N8N_API_KEY"])
workflows = gateway.list_workflows()
assert len(workflows) == 1, f"expected one HADES canary, got {len(workflows)}"
workflow = workflows[0]
assert workflow["id"] == "epsilon-server-health-watch-core"
assert workflow["template_id"] == "server-health-watch"
assert workflow["owner"] == "owner"
assert workflow["approved"] is True
assert workflow["active"] is False
assert workflow["trigger"] == "schedule"
assert set(workflow) == {
    "id", "template_id", "owner", "shared_groups", "active", "trigger",
    "next_run", "approved",
}
assert not any(key in workflow for key in ("nodes", "credentials", "executions", "data"))

executions = gateway.list_executions(workflow["id"], limit=1)
assert len(executions) <= 1
if executions:
    assert set(executions[0]) == {"startedAt", "status"}

print("PASS live n8n adapter returned bounded HADES metadata")
print(f"PASS live n8n execution projection returned {len(executions)} row(s)")
PY
