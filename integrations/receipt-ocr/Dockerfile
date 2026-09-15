# Disposable/staging worker only. Keep OCR isolated from the HADES host.
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    "paddleocr-mcp[local-cpu]==0.8.5"

ENV HOME=/tmp/hades-ocr
ENV FLAGS_use_mkldnn=0
RUN mkdir -p /tmp/hades-ocr && chown -R 65532:65532 /tmp/hades-ocr
USER 65532:65532
ENTRYPOINT ["paddleocr_mcp"]
