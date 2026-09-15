# ADR: receipt and document OCR

Status: **SELECTED / STAGED; MCP CLI VERIFIED**

## Decision

Evaluate the official PaddleOCR MCP path first, using its self-hosted serving
mode. PaddleOCR is a maintained upstream document/OCR project with a current
OCR pipeline, document parsing options, and an official MCP integration. The
first deployment target is local/self-hosted CPU or GPU inference; hosted OCR
is not part of the household acceptance contract.

References:

- https://github.com/PaddlePaddle/PaddleOCR
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/integrations/mcp_server.md
- https://www.paddleocr.ai/main/en/version3.x/inference_deployment/serving/serving.html

## Boundary

```text
receipt image
    -> PaddleOCR evidence
    -> Hermes interpretation/normalization
    -> Grocy product candidates
    -> owner review preview
    -> explicit intake apply
```

OCR output is evidence. It cannot directly mutate Grocy or Actual Budget. A
single receipt must not silently create both a household intake and a finance
transaction. Those are separate previews and confirmations against their
separate canonical systems.

The initial MCP surface should expose extraction only. It must not expose
filesystem traversal, arbitrary URL fetch, shell execution, or direct Grocy
writes. Input size, MIME type, page count, and processing time are bounded.

## Acceptance contract

The receipt adapter is not green until it can return merchant/date/total and
line-item evidence with confidence, preserve the original evidence reference,
and distinguish unavailable/partial OCR from a successful extraction. A line
such as `BAN ORG` must become a review candidate, not silently become
`Bananas`. Grocy matching and intake remain explicit and reversible where the
canonical API permits it.

Disposable dogfood must cover a clean synthetic receipt, poor image/partial
OCR, tax and total mismatch, duplicate receipt submission, unknown product,
corrected match, cancel, restart, and canonical Grocy verification. Real
receipts and owner credentials are not required for this staging work.

The current evidence contract is implemented in
`integrations/receipt-ocr/evidence.py` and exercised by
`scripts/test-receipt-ocr-contract.sh`. It has not yet claimed PaddleOCR
runtime accuracy; that requires a disposable PaddleOCR deployment and sample
images.

The official `paddleocr-mcp==0.8.5` CLI was also verified in a disposable
Python 3.14 virtual environment. The package and CLI install successfully
without local inference extras and expose the documented self-hosted mode.
The `local-cpu` extra cannot currently resolve on this host because no
compatible `paddlepaddle` distribution is available for Python 3.14. This is
an environment compatibility result, not a reason to add a custom OCR engine;
the next evaluation should use a supported Python/runtime guest or a bounded
self-hosted PaddleX service. The same pinned dependency set resolves in the
already available disposable Python 3.11 container, including
`paddlepaddle==3.3.1`; this does not authorize installing OCR into the
production HADES host.

The disposable worker now completes a synthetic CPU receipt inference when the
oneDNN path is disabled (`FLAGS_use_mkldnn=0` and
`enable_mkldnn=False`). It recognizes the merchant, item names, and printed
totals; the repeatable check is
`scripts/test-receipt-ocr-runtime.sh`. The default oneDNN path reproduced the
upstream `ConvertPirAttribute2RuntimeAttribute` failure documented in the
[PaddleOCR issue tracker](https://github.com/PaddlePaddle/PaddleOCR/issues/18162),
so the fallback is part of the isolated worker contract and not hidden as an
HADES parser workaround.

The official MCP `ocr` tool was then inspected over stdio. Its upstream input
contract accepts absolute filesystem paths and HTTP(S) URLs, so it must not be
registered directly in Hermes. `integrations/receipt-ocr/input_boundary.py`
defines the required HADES-owned firewall: bounded inline PNG/JPEG/WebP data
only, with path/URL rejection and MIME/magic-byte validation. A thin wrapper
must enforce this contract before delegating to the upstream MCP; direct MCP
registration is therefore rejected as a security-boundary failure.

The implemented `integrations/receipt-ocr/gateway.py` is that wrapper: it
exposes only `receipt_ocr_extract`, passes a validated data URL to the official
upstream `ocr` tool over local stdio, and keeps Grocy/finance writes outside
the OCR process.

The gateway image was rebuilt as `hades-receipt-ocr:gateway-staged`; an
image-backed MCP handshake exposed only `receipt_ocr_extract`, and a path
input was rejected before the upstream worker was called. This proves the
container transport and input boundary, not yet representative messy-receipt
accuracy or Grocy intake application.

The reproducible isolated worker definition is
`integrations/receipt-ocr/Dockerfile`. It pins Python 3.11 and the official
MCP package, and includes the native OpenCV/Paddle runtime libraries. The
worker is intentionally not part of the production Compose set until a
disposable image can complete actual OCR on representative synthetic images.

## Non-decision

Do not build an HADES OCR engine, receipt database, or shadow finance ledger.
If PaddleOCR’s resource requirements or output contract fail the disposable
evaluation, revisit another maintained upstream implementation before writing
custom code.
