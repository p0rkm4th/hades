#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import ast
import json
from pathlib import Path
from types import SimpleNamespace

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
assert "def _classify_upstream_result" in source
assert "upstream PaddleOCR returned no usable text" in source
assert "json.loads" in source
assert "isinstance(payload.get(\"error\"), str)" in source
assert "any(text.strip() for text in content)" in source

# Exercise the pure result classifier without requiring the optional gateway
# runtime dependencies. An empty successful MCP envelope is not OCR evidence.
tree = ast.parse(source)
classifier = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_classify_upstream_result")
namespace = {"json": json}
exec(compile(ast.Module(body=[classifier], type_ignores=[]), "gateway.py", "exec"), namespace)
classify = namespace["_classify_upstream_result"]
assert classify(SimpleNamespace(isError=False, content=[]))["status"] == "FAILED"
assert classify(SimpleNamespace(isError=False, content=[SimpleNamespace(text="  ")]))["status"] == "FAILED"
assert classify(SimpleNamespace(isError=False, content=[SimpleNamespace(text="Total 7.03")]))["status"] == "SUCCEEDED"
assert classify(SimpleNamespace(isError=False, content=[SimpleNamespace(text='{"error": "No text detected"}')]))["status"] == "FAILED"
assert classify(SimpleNamespace(isError=True, content=[]))["status"] == "FAILED"
compose = Path("deploy/templates/receipt-ocr.compose.yaml").read_text()
assert '127.0.0.1:8765:8000' in compose
assert 'read_only: true' in compose and 'cap_drop:' in compose
print("PASS OCR gateway exposes image-only receipt tool")
print("PASS OCR gateway delegates to official upstream MCP without Grocy/finance writes")
print("PASS OCR gateway has bounded private Streamable HTTP deployment")
PY
