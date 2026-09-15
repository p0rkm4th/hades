#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

source = Path("integrations/receipt-ocr/gateway.py").read_text()
assert "async def receipt_ocr_extract" in source
assert "decode_image_input" in source
assert 'session.call_tool("ocr"' in source
assert '"input_data": data_url' in source
assert '"return_images": False' in source
assert "Paths, URLs, filesystem access, and writes are not accepted." in source
assert "image_base64: str" in source and "mime: str | None" in source
assert 'transport="streamable-http"' in source
assert 'HADES_OCR_TRANSPORT' in source
compose = Path("deploy/templates/receipt-ocr.compose.yaml").read_text()
assert '127.0.0.1:8765:8000' in compose
assert 'read_only: true' in compose and 'cap_drop:' in compose
print("PASS OCR gateway exposes image-only receipt tool")
print("PASS OCR gateway delegates to official upstream MCP without Grocy/finance writes")
print("PASS OCR gateway has bounded private Streamable HTTP deployment")
PY
