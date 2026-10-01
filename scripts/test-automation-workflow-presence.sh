#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
from integrations.automation import workflow_presence


class Runner:
    def __init__(self, workflows):
        self.workflows = workflows

    def list_workflows(self):
        if isinstance(self.workflows, Exception):
            raise self.workflows
        return self.workflows


assert workflow_presence(None, "workflow-1") is False
assert workflow_presence(Runner([]), None) is False
assert workflow_presence(Runner([{"id": 1}]), "1") is True
assert workflow_presence(Runner([{"id": "workflow-2"}]), "workflow-1") is False
assert workflow_presence(Runner(RuntimeError("synthetic runner outage")), "workflow-1") is None
print("PASS workflow reconciliation distinguishes present, absent, and unknown")
PY
