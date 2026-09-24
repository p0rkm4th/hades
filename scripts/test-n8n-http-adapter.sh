#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import json
from integrations.automation import N8NHttpGateway
import integrations.automation.n8n_http as adapter

calls = []

class Response:
    def __init__(self, payload): self.payload = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return self.payload

def fake_urlopen(request, timeout):
    calls.append((request.full_url, dict(request.header_items()), timeout))
    if "/workflows" in request.full_url:
        return Response({"data": [{
            "id": "n8n-1", "name": "private-hidden", "active": True,
            "nextRun": "synthetic", "tags": [
                {"name": "hades-template:shw"},
                {"name": "hades-owner:owner"}, {"name": "hades-group:hades-household"},
                {"name": "hades-trigger:weekly"}, {"name": "hades-approved:false"},
            ], "nodes": [{"credentials": {"secret": "must-not-escape"}}],
        }, {"id": "other", "nodes": [{"parameters": {"secret": "hidden"}}]}]})
    return Response({"data": [{"startedAt": "synthetic", "status": "success", "data": {"secret": "hidden"}}]})

adapter.urlopen = fake_urlopen
assert adapter._NoRedirectHandler().redirect_request(None) is None
try:
    N8NHttpGateway("file:///tmp/n8n", "synthetic-key")
except ValueError:
    pass
else:
    raise AssertionError("non-HTTP n8n endpoint accepted")
gateway = N8NHttpGateway("https://n8n.invalid", "synthetic-key")
workflows = gateway.list_workflows()
assert workflows[0] == {
    "id": "n8n-1", "template_id": "server-health-watch", "owner": "owner",
    "shared_groups": ("hades-household",), "active": True, "trigger": "weekly",
    "next_run": "synthetic", "approved": False,
}
assert workflows[1]["template_id"] == ""
assert gateway.list_executions("n8n-1") == ({"startedAt": "synthetic", "status": "success"},)
assert "X-n8n-api-key" in calls[0][1] and calls[0][1]["X-n8n-api-key"] == "synthetic-key"
assert all("secret" not in repr(item) for item in (workflows, gateway.list_executions("n8n-1")))
assert "limit=100" in calls[0][0]
assert "workflowId=n8n-1" in calls[1][0]
print("PASS n8n adapter normalizes metadata without workflow nodes or payloads")
print("PASS n8n adapter uses bounded authenticated reads")
PY
