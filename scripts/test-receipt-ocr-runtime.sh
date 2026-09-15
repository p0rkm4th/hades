#!/usr/bin/env bash
set -euo pipefail

image=${HADES_RECEIPT_OCR_IMAGE:-hades-receipt-ocr:staged}
docker image inspect "$image" >/dev/null
output=$(docker run --rm \
  -v hades-paddle-cache:/tmp/hades-ocr \
  -e FLAGS_use_mkldnn=0 \
  --entrypoint python "$image" -c '
from PIL import Image, ImageDraw
from pathlib import Path
from paddleocr import PaddleOCR

path = Path("/tmp/receipt.png")
image = Image.new("RGB", (1000, 1400), "white")
draw = ImageDraw.Draw(image)
lines = ["SYNTHETIC MARKET", "2026-09-14", "Milk                 3.49",
         "Bananas              1.29", "Subtotal             4.78",
         "Tax                  0.48", "Total                5.26"]
for index, line in enumerate(lines):
    draw.text((80, 100 + index * 120), line, fill="black")
image.save(path)

ocr = PaddleOCR(lang="en", device="cpu", enable_mkldnn=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)
result = next(iter(ocr.predict(str(path))))
recognized = set(result["rec_texts"])
required = {"SYNTHETIC MARKET", "Milk", "Bananas", "Subtotal", "Tax", "Total", "5.26"}
assert required <= recognized, (required - recognized, recognized)
print("OCR_RUNTIME_OK")
' 2>&1)
grep -q 'OCR_RUNTIME_OK' <<<"$output"
echo 'PASS isolated PaddleOCR CPU inference on synthetic receipt'
