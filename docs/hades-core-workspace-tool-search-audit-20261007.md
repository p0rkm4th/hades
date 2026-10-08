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

## HADES compatibility finding

The current HADES workspace turn replaces `self.tools` with only the selected
read-only or action definitions. Its Tool Search bridge dispatcher rebuilds
the deferred catalog from enabled/disabled toolsets, and its scoped deferred
name filter applies household and domain denials but does not intersect the
current agent's `valid_tool_names`. The bridge dispatcher also receives
toolset lists rather than the current turn's workspace permission set.

Therefore, merely enabling native deferral for the three action tools would
not preserve the existing diagnosis boundary: the bridge could rediscover or
dispatch an action tool even when HADES intended the turn to allow only
`read_file` and `search_files`. The direct-call check is not sufficient because
bridge calls are authorized by the separate deferred-tool path.

## Decision

**HOLD; do not enable native Tool Search for workspace tools in the current
HADES integration.** The stable-schema opportunity is credible, but adopting it
now would weaken per-turn tool scoping. The earlier constant-five-schema
experiments also had diagnosis-time rejected action attempts and unreliable
verification, so schema stability alone does not establish better usability.

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
allowlist. The workspace runtime regression exercises all three bridge calls
inside a diagnosis turn. A synthetic parser probe against the production-pinned
Hermes 0.21.2 runtime passed for the three denials and the allowed `read_file`
case. The full Hermes 0.21.5 workspace runtime harness still needs its staged
Hindsight client/plugin dependencies to be made available before it can run
locally; the public CI run verifies source composition and static contracts,
not this runtime behavior.

Nyx also confirmed that deferring the five core workspace tools is not a
promising latency fix: Hermes keeps core tools eager unless explicitly
configured, and deferral replaces tools with three bridge schemas plus extra
search/describe/call steps. Keep the native deferral experiment on hold; pursue
the measured action-prefix/cache gap through a matched diagnostic instead.
