# Hermes native Tool Search and workspace scope audit — 2026-10-07

## Question

Can stable Hermes Tool Search keep HADES' workspace tool schema stable between
read-only diagnosis and an explicit action turn, without exposing mutative
tools outside the action turn?

## Upstream behavior

The exact staged Hermes v0.21.5 source (`v2026.9.24`) accepts an explicit
`tools.tool_search.defer` list of tool names. A direct probe of the tagged
`ToolSearchConfig` and `assemble_tool_defs` used the native five-tool workspace
catalog (`read_file`, `search_files`, `write_file`, `patch`, `terminal`). With
no deferred names, Hermes returned all five definitions. With `write_file`,
`patch`, and `terminal` deferred, Hermes returned the two read schemas plus the
three stable bridge schemas (`tool_search`, `tool_describe`, `tool_call`). This
shows a possible stable model-facing schema; it does not show a model behavior,
latency, or cache improvement.

Hermes documents Tool Search as progressive disclosure for schemas, and its
tagged implementation allows explicitly named core tools to be deferred:
[Hermes v0.21.5 release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.24),
[tagged Tool Search implementation](https://github.com/NousResearch/hermes-agent/blob/v2026.9.24/tools/tool_search.py).
Ollama exposes prompt-evaluation and prompt-cache token counts, so a matched
runtime benchmark can verify whether the proposed stable prefix actually
improves reuse:
[Ollama usage metrics](https://github.com/ollama/ollama/blob/main/docs/api/usage.mdx).

## HADES compatibility finding: original gap closed; deferred target scope remains

At the time of the original audit, HADES workspace turns replaced `self.tools`
with only the selected read-only or action definitions, while the Tool Search
bridge dispatcher rebuilt the deferred catalog from enabled/disabled
toolsets. Its deferred-name filter applied household and domain denials but
did not intersect the current agent's `valid_tool_names`; the dispatcher also
received toolset lists rather than the current turn's workspace permission
set.

That made enabling native deferral unsafe for workspace tools: the bridge
could rediscover or dispatch an action tool during diagnosis. The raw
bridge-name gate added in commit `3e1663e` closes the current parser entry
point by requiring the bridge schema name itself to appear in
`agent.valid_tool_names`. Workspace turns omit all three bridge names, so they
are rejected before deferred dispatch. If a future workspace configuration
explicitly adds those bridge schemas, the downstream deferred target filter
still needs to intersect the authenticated turn's exact allowed-name set.

## Decision

**HOLD native Tool Search for workspace tools in the current HADES
integration.** The raw bridge-name authorization gap described below has been
closed, and the runtime contract now verifies that bridge calls absent from
the active turn catalog are rejected. Directly exposing five schemas with an
exact read-only diagnosis allowlist is also safe in the focused contract, but
the corrected-reset four-repeat comparison restored action cache reuse while
increasing model/tool calls and failing to improve end-to-end latency. See the
[controlled workspace cache report](hades-core-workspace-prefix-cache-diagnostic-2026-10-07.md).
That stable-schema candidate is rejected as a product fix. Native deferral
would additionally replace core schemas with bridges and add discovery steps;
it has not demonstrated owner value.

Revisit only after the deferred search, describe, and call path can receive and
enforce the authenticated per-turn allowed-name set before exposing or
dispatching deferred definitions. Then compare the native path against the
current two-to-five-schema transition using repeated, order-balanced workspace
tasks, with diagnosis mutation attempts, tool exposure, cache tokens, task
completion, fresh test evidence, and latency reported separately. Keep
production settings and `main` unchanged pending that qualification.

## Follow-up authorization review

An independent review found that Hermes' parser unwrapped `tool_call` and
HADES' direct-call guard then returned early for all raw bridge calls. The
bridge's separate profile-toolset scope could therefore accept a forged or
unexpected `tool_search`, `tool_describe`, or `tool_call` during a workspace
turn, even though those bridge schemas were absent from that turn's selected
tool catalog. This was a parser-boundary gap; no evidence showed the model had
used it in owner traffic.

HADES now requires the raw bridge name itself to appear in the current agent's
`valid_tool_names` before the parser permits that bridge call. Workspace
diagnosis and action turns omit all bridge names, so all three are rejected
there while direct read tools remain governed by the existing exact phase
allowlist. The workspace runtime regression exercises `tool_search`,
`tool_describe`, and `tool_call` inside a diagnosis turn. The full Hermes
0.21.5 runtime harness was run with the staged Hindsight client/plugin and an
actual isolated rootless Docker 29.8.2 daemon holding the pinned sandbox image.
It passed the bridge denials, owner workspace mount, no-network check,
diagnosis/action catalog boundaries, fabricated-result handling,
verification-claim handling, ordinary follow-up reset, household denial, and
per-owner workspace separation. A separate parser probe against production-
pinned Hermes 0.21.2 also denied all three bridges while allowing
`read_file`.

Nyx also confirmed that deferring the five core workspace tools is not a
promising latency fix: Hermes keeps core tools eager unless explicitly
configured, and deferral replaces tools with three bridge schemas plus extra
search/describe/call steps. Keep native deferral on hold. The direct
stable-schema experiment established that action prefix caching can be
restored, but it increased total calls/results and did not reduce the paired
HADES latency gap; retain the dynamic catalog while reducing actual task
calls and invalid tool attempts.
