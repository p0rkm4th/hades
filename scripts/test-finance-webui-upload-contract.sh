#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

route = Path("webui/finance_upload_compat.py").read_text()
ui = Path("webui/finance-upload.js").read_text()
dockerfile = Path("webui/Dockerfile").read_text()
entrypoint = Path("webui/entrypoint.sh").read_text()
compose = Path("deploy/templates/open-webui.compose.yaml").read_text()

assert "/api/v1/hades/finance/preview" in route
assert "/api/v1/hades/finance/inspect" in route
assert "HADES_FINANCE_OWNER_USER_ID" in route
assert "Finance CSV preview is owner-only" in route
assert "10 * 1024 * 1024" in route
assert "preview_file" in route
assert "writes_performed" not in route  # route delegates; no ad-hoc writer
assert "/api/v1/hades/finance/preview" in ui
assert "new FormData()" in ui
assert "target_account_id" in ui and "mapping_json" in ui
assert "Only CSV uploads are accepted" in ui or ".csv,text/csv" in ui
assert "webui/finance_upload_compat.py" in dockerfile
assert "integrations/actual-finance-import" in dockerfile
assert "finance-upload.js" in entrypoint  # stale injected tags are removed on startup
assert 'position:fixed;right' not in ui  # the review dialog may still be modal; the action itself is not global
assert 'hades-finance-csv-button' not in ui
assert 'hades-finance-csv-contextual-button' in ui
assert 'uploadedFiles' in ui and '/content' in ui
assert 'Review CSV' in ui
assert 'finance-upload.js?v=$asset_version\\"></script>' in entrypoint
assert "HADES_FINANCE_OWNER_USER_ID" in compose
print("PASS WebUI finance CSV control is same-origin and confirmation-safe")
print("PASS finance upload route is owner-ID gated and non-persistent")
print("PASS Open WebUI artifact includes finance upload assets and parser")
PY
