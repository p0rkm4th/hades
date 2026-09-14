# Performance campaign

This campaign measures user-visible stages, not isolated function overhead.
Production remains unchanged; synthetic fixtures are used for provider paths
that lack owner authorization.

The overlay now emits bounded `HADES timing stage=tool` and `stage=turn` log
records. These contain only the tool name, selected model, and elapsed
milliseconds—never arguments or response content—so stage attribution can be
captured without adding a tracing dependency or exposing private data.

| Workflow | Evidence | Bottleneck / disposition |
|---|---|---|
| Normal chat | Existing owner smoke evidence | Model inference; no new defect isolated |
| Memory recall/correction | Owner persistence evidence and async-retain timing | Hindsight extraction is asynchronous; do not treat immediate recall as proof |
| Grocy read | 40.79s total; model 24.8s + 15.8s continuation; Grocy 0.03s | Local model and continuation, not adapter |
| Grocy mutation | Concurrent synthetic adds 24.68s/26.86s; tool calls ~0.04s | Model/continuation; canonical duplicate merge held |
| Recipe request | Synthetic authoring/fulfillment contract | Provider timing still needs owner-visible recipe dogfood |
| Web search | Candidate/API freshness evidence | Model/tool loop and search latency need fresh owner-session sample |
| Multi-domain request | Routing contracts and contradiction fixture | End-to-end sample remains useful; no blind optimization justified |
| Agent Zero delegation | Bounded bridge contract; weak model needed three attempts | Tool description/model selection quality; real operator remains owner-gated |

The current actionable threshold is a workflow that repeatedly exceeds roughly
30 seconds or loops unnecessarily. Existing measurements point to local-model
inference and post-tool continuation as the first optimization targets. No
Grocy retry, token-ceiling tweak, or adapter rewrite is justified by current
evidence; the next measurement should capture first model call, tool call,
continuation, and total duration for one fresh owner-approved web and recipe
turn.
