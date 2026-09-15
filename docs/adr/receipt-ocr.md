# ADR: receipt and document OCR

Status: **SELECTED / STAGED FOR DISPOSABLE EVALUATION**

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

## Non-decision

Do not build an HADES OCR engine, receipt database, or shadow finance ledger.
If PaddleOCR’s resource requirements or output contract fail the disposable
evaluation, revisit another maintained upstream implementation before writing
custom code.
