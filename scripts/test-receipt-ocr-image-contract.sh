#!/usr/bin/env bash
set -euo pipefail

dockerfile=integrations/receipt-ocr/Dockerfile
grep -q '^FROM python:3.11-slim-bookworm$' "$dockerfile"
grep -q 'libgomp1 libgl1 libglib2.0-0' "$dockerfile"
grep -q 'paddleocr-mcp\[local-cpu\]==0.8.5' "$dockerfile"
grep -q '^USER 65532:65532$' "$dockerfile"
grep -q '^ENV HOME=/tmp/hades-ocr$' "$dockerfile"
grep -q '^ENV FLAGS_use_mkldnn=0$' "$dockerfile"
grep -q '^COPY gateway.py input_boundary.py /opt/hades-receipt-ocr/$' "$dockerfile"
grep -q 'paddleocr_mcp' "$dockerfile"
echo 'PASS isolated OCR worker pins supported runtime and native prerequisites'
echo 'PASS isolated OCR worker runs without root and exposes official MCP CLI'
