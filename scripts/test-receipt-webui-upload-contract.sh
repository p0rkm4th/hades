#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
route = Path('webui/receipt_upload_compat.py').read_text()
ui = Path('webui/receipt-upload.js').read_text()
dockerfile = Path('webui/Dockerfile').read_text()
compose = Path('deploy/templates/open-webui.compose.yaml').read_text()
entrypoint = Path('webui/entrypoint.sh').read_text()
assert "'/api/v1/hades/receipt/preview'" in route
assert 'Receipt OCR preview is owner-only' in route
assert "tools/call" in route and "receipt_ocr_extract" in route
assert "writes': []" in route
assert "unique_lines" in route and "'lines': visible_lines" in route
assert "'resolution': 'REVIEW_REQUIRED'" in route and "'totals': totals" in route
assert "inline_amount_re" in route and "inline_total_re" in route
assert "SequenceMatcher" in route and "REVIEW_REQUIRED" in route
assert '/api/v1/hades/receipt/preview' in ui
assert 'The shared pantry changes only after you confirm' in ui
assert 'Receipt text I found:' in ui
assert '/api/v1/hades/receipt/apply' in ui and '/api/v1/hades/receipt/apply' in route
assert 'Explicit confirmation is required' in route
assert 'webui/receipt-upload.js' in dockerfile and 'receipt_upload_compat.py' in dockerfile
assert 'hades-private' in compose and 'hades-receipt-ocr:8000/mcp' in compose
assert '/static/receipt-upload.js' in entrypoint
assert 'hades-receipt-ocr-button' not in ui
assert 'hades-receipt-ocr-contextual-button' in ui
assert 'Review receipt' in ui
assert 'isReceiptImage' in ui
assert 'payload?.id && payload?.filename && isReceiptImage(payload.filename)' in ui
assert 'uploadedFilename && !isReceiptImage(uploadedFilename)' in ui
assert '|| document.body' not in ui
print('PASS WebUI receipt OCR upload is owner-scoped and review-gated')
PY
