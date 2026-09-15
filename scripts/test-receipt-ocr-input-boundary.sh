#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
from pathlib import Path

path = Path("integrations/receipt-ocr/input_boundary.py")
spec = importlib.util.spec_from_file_location("input_boundary", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

png = b"\x89PNG\r\n\x1a\n" + b"synthetic"
encoded = __import__("base64").b64encode(png).decode()
result = module.decode_image_input(encoded, declared_mime="image/png")
assert result["bytes"] == png and result["mime"] == "image/png"
assert module.decode_image_input(f"data:image/png;base64,{encoded}")["size_bytes"] == len(png)

for unsafe in ("/etc/passwd", "https://example.test/receipt.jpg", "file:///tmp/a.png", "not-base64"):
    try:
        module.decode_image_input(unsafe)
    except module.ImageInputError:
        pass
    else:
        raise AssertionError(f"unsafe OCR input accepted: {unsafe}")

try:
    module.decode_image_input(encoded, declared_mime="image/jpeg")
except module.ImageInputError:
    pass
else:
    raise AssertionError("MIME mismatch accepted")

print("PASS OCR firewall accepts bounded inline image data")
print("PASS OCR firewall rejects paths, URLs, malformed data, and MIME mismatch")
PY
