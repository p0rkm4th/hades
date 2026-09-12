# Hermes Compatibility Overlay Inventory

`hermes/sitecustomize.py` is a deployment overlay, not a HADES runtime. Each
behavior below has an explicit reason to exist and a removal condition. The
overlay must be re-evaluated whenever the pinned Hermes version changes.

| Behavior | Upstream gap or deployment constraint | Evidence / regression check | Removal condition |
|---|---|---|---|
| Register packaged SearXNG at startup | Lazy plugin discovery can race legacy web-tool resolution | Composition smoke check and Hermes health | Upstream discovery is deterministic and web-search owner workflow passes without it |
| Make Hindsight retain asynchronous | Synchronous local extraction can exceed chat timeout while Ollama shares the GPU | Hindsight/API tests and owner memory persistence workflow | Upstream retain is asynchronous by default and latency/persistence pass without the patch |
| Bound and normalize Hindsight retain/recall | Small models can recurse through reflection or surface duplicate, low-specificity facts | Memory regression plus fresh owner recall/correction evidence | Upstream offers the same bounded tool/result contract and fresh owner workflow passes |
| Reconcile and narrow Grocy MCP tools | API-agent construction can precede dynamic MCP discovery; mixed prompts need least privilege | Grocy canonical-state workflows and memory/household composition | Native discovery supplies equivalent tools before agent construction and owner contracts pass |
| Route external-source and memory intents to a tool-capable model | Current completion-only/weak local models are unsuitable for reliable tool calls | Model capability registration and owner model/tool workflows | Upstream capability routing provides equivalent behavior |
| Isolate completion-only creative models from HADES tools | Uncensored/creative models are intentionally tool-less | Owner model-picker labels and no-tool workflow | A reviewed safety policy explicitly replaces this deployment boundary |
| Preserve authoritative Hindsight output in streamed turns | Some local models emit a misleading continuation after a successful memory call | Memory regression and mobile DOM recall/correction evidence | Upstream streaming preserves the authoritative tool result |

## Review rule

No behavior is removed solely because an upstream test suite passes. Its
removal condition must include the affected HADES owner workflow, canonical
backend verification where applicable, and reload/restart persistence when it
affects state. Production remains pinned while the full external-contract
matrix is not isolated from authoritative owner data.
