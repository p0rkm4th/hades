# Performance campaign

This campaign measures user-visible stages, not isolated function overhead.
Production remains unchanged; synthetic fixtures are used for provider paths
that lack owner authorization.

The overlay now emits bounded `HADES timing stage=tool` and `stage=turn` log
records. These contain only the tool name, selected model, and elapsed
milliseconds—never arguments or response content—so stage attribution can be
captured without adding a tracing dependency or exposing private data.
For the SearXNG-backed profile, web routing exposes `web_search` only; the
search-only backend cannot support `web_extract`.

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

## Disposable weak-model lane — 2026-09-14

Direct Ollama tool-schema probes used the installed Qwen 8B lane without HADES
credentials or provider state. With a 400-token bounded completion allowance,
Qwen selected the correct tool for all four domains: web search, canonical
Grocy stock, private-memory recall, and bounded Agent Zero delegation. Direct
generation took roughly 5.1–7.1 seconds per selection. A lower 100-token cap
ended during reasoning before the pantry call, so the cap is a real interface
parameter rather than an optimization target.

The same lane correctly selected the initial Grocy stock read in a multi-turn
conversation, then declined to invent recipe inputs for an underspecified
“what are we missing?” follow-up and did not apply the ambiguous “add whatever
is missing but do not add onions” request. This preserves preview/confirmation
semantics; a future recipe-quality run should provide an explicit recipe and
normalized item list. Dolphin-Mistral rejected the tool-call API request and
remains a completion-only lane, consistent with its policy classification.

Qwen 14B was run against the identical schema and four prompts. It also
selected web, Grocy, private memory, and Agent Zero correctly, at approximately
6.0–15.5 seconds per selection (web was slowest). This is comparative evidence
for tool usability, not a benchmark or a production-model change; the existing
HADES routing policy remains unchanged.

Both Qwen 8B and 14B were also given four synthetic contradictions without
tools. They selected the canonical value in each case (Proxmox runtime,
Grocy pantry, Actual finance, Kuma availability) and explained that remembered
or web values could be stale. At a 240-token cap, both lanes sometimes ended
while still reasoning, and their answers were more verbose than a daily-driver
response. This validates authority preference only; it does not replace an
authenticated HADES end-to-end answer-quality run.

An eight-turn Qwen 8B conversation covering explicit retain, Grocy read,
correction retain, web search, an abandoned mutation, topic switch, ambiguous
pronoun mutation, and recall completed cleanly at a 400-token allowance. The
model made no tool call for the abandoned or ambiguous mutations. The same
sequence at 220 tokens exhausted reasoning on several turns, especially for a
third isolated user. This is a completion-budget/context-quality limitation,
not evidence to lower the production cap; the full HADES multi-user run still
needs authenticated gateway execution.
