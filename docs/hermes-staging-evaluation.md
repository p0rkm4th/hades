# Hermes upstream staging evaluation

Status: staging evidence collected; production remains pinned.

## Candidate

The current upstream tagged release is [Hermes Agent v0.21.2, released as
`v2026.9.11`](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.11).
It was evaluated in an isolated checkout and Python environment under `/tmp`;
the production Hermes service and profile were not modified.

## Verified in the isolated environment

- Upstream CLI reports Hermes Agent `0.21.2` on Python 3.11.
- Upstream gateway help and key modules compile successfully.
- Focused clean-upstream contract run: **390 passed**, 18 deselected, covering
  A2A, Hindsight, API-server, and gateway behavior.
- Native A2A schema, plugin, gating, and reason-roundtrip tests: **117 passed**.
- Hindsight provider, API-server toolset, and normalization tests: **97
  passed** after installing the declared `hindsight-client==0.6.1` staging
  dependency.
- ACP adapter and protocol contract tests: **154 passed**, 2 warnings, after
  installing the declared `agent-client-protocol==0.9.0` staging extra. The
  dependency was not added to production.
- Clean upstream API-server owner-contract smoke also passed for a normal
  Open WebUI conversation: the isolated model returned the exact requested
  marker through the temporary Open WebUI connection. A synthetic MCP probe
  first exposed a missing optional dependency: the clean checkout had not
  installed the declared `mcp` extra. After installing the exact upstream
  `mcp==2.0.0`, `httpx2==2.7.0`, and `starlette==1.3.1` staging extra, the
  server registered five tools. A deterministic synthetic provider then drove
  `tool_search` → `tool_call`; the MCP process wrote `CLEAN-MCP-READY`, and
  Hermes returned that same marker after post-tool continuation. No owner or
  production data was used.

These are upstream contract tests, not owner acceptance. No staging process
was pointed at production Grocy, Hindsight, Agent Zero, or owner credentials.

## Compatibility disposition

| HADES behavior | Initial disposition | Reason |
|---|---|---|
| Hindsight provider loading and async retain support | Re-test against upstream | The candidate has native Hindsight provider tests and a declared client dependency. |
| API-server streaming/tool lifecycle | PASS in isolated contract staging | Normal Open WebUI streaming passed; with the declared MCP extra installed, the synthetic provider exercised tool search, MCP invocation, and post-tool continuation with a canonical marker. |
| Native Agent Zero A2A | Retain MCP bridge for now | Hermes `0.21.2` contains native A2A support and its focused suite passes, but the deployed Agent Zero A2A server is disabled. Enabling it would require a new authenticated exposure and owner-visible lifecycle contract. |
| HADES model-intent routing | Retain for now | This is deployment policy for local models and domain tools, not generic Hermes functionality. |
| HADES Grocy tool reconciliation | Retain for now | It compensates for the deployment's dynamic MCP discovery boundary and must be tested against the candidate before removal. |
| Hindsight result normalization / explicit-memory narrowing | Retain for now | These are HADES owner-contract safeguards; remove only after a real staged owner workflow proves upstream parity. |
| Completion-only model isolation | Retain for now | This is an HADES safety policy independent of upstream version. |

## Decision

Do not upgrade production yet. The clean Hermes conversation, MCP contract,
and ACP contract now pass in isolated staging, but the full Hindsight, Grocy,
SearXNG, Agent Zero, Open WebUI upgrade, and rollback matrix remains
incomplete. Prepare a rollback-safe migration only after those contracts pass,
then delete only compatibility behavior proven obsolete. Production remains
pinned meanwhile.

## Follow-up local-model owner-contract probe

On 2026-09-13, the isolated candidate gateway was restarted twice using the
locally available `gemma4:12b` model. Hermes 0.21.2 reported healthy, a normal
OpenAI-compatible chat returned the exact marker `CLEAN-GEMMA-OWNER-READY`,
and a native stdio MCP server was discovered and called through the API path;
the post-tool response returned `CLEAN-MCP-GEMMA-READY`. This is a bounded
candidate smoke result, not production acceptance.

The same profile exposed a real configuration constraint: local Qwen 3 8B and
14B advertise 40K context (and the earlier probe reported 32K for 8B), while
Hermes 0.21.2 enforces a 64K minimum. The candidate therefore cannot use
those profiles without a model/runtime change. `gemma4:12b` advertises 262K
context and is a viable staging candidate. The full isolated Hindsight,
Grocy, SearXNG, Agent Zero, Open WebUI, and rollback matrix remains incomplete;
production stays on Hermes 0.14.0.

## 0.21.2 HADES composition checkpoint

The disposable candidate was also run as a HADES composition with Hermes
0.21.2, `gemma4:12b`, synthetic Hindsight, synthetic Grocy, and the existing
HADES overlay. The candidate remained healthy and native MCP registration
loaded both the deterministic fixture and synthetic Grocy. Upstream-only
testing confirmed that `X-Hermes-Session-Key` identifies a session but does
not select Hindsight's `{user}` bank. With the overlay, a trusted
`hades-user-*` session selected the isolated bank and the direct retain tool
completed.

The exact-bank Hindsight assertion now passes: the trusted candidate session
selected `hades-user-candidate-alpha`, the retain completed in that bank, and
canonical recall returned the retained synthetic marker from that same bank.
The write is asynchronous, so the acceptance check waits for the Hindsight
operation to complete before reading it. Immediate recall is intentionally
not treated as proof of persistence.

Remaining promotion gaps:

- Local Gemma fact extraction took roughly
  50–85 seconds, so immediate recall can miss a newly accepted fact. The
  candidate acceptance test now accounts for this asynchronous behavior.
- A separate synthetic SearXNG endpoint and a bounded Agent Zero staging
  bridge have not been provisioned; production endpoints remain deliberately
  excluded from candidate testing.

The candidate also showed auxiliary title-generation timeouts and inherited a
large staging context file. These affect candidate ergonomics/performance but
did not alter production. No production service or data was changed.

The candidate then passed a real web-search turn after enabling the upstream
`web` toolset and the disposable SearXNG JSON endpoint: Hermes executed
`web_search`, SearXNG returned results, and Gemma produced a result from that
response. The HADES overlay's direct web-intent narrowing is retained because
the same model previously attempted to route deferred `web_search` through
`tool_call`, which Hermes correctly rejected.

After the web change, the candidate was restarted and passed its health and
authenticated model-list checks; the overlay syntax and capability-boundary
regression also passed. The candidate was then shut down cleanly. A bounded
Agent Zero success was not claimed: production Agent Zero and its credentials
were not used, while the disposable native A2A probe remains incompatible
with Hermes' expected agent-card transport. The existing narrow MCP bridge
therefore remains the only approved operator path, pending a separate
disposable bridge/credential fixture.

That fixture was subsequently supplied locally: the checked-in MCP bridge
ran against a loopback-only synthetic Agent Zero HTTP server. Hermes 0.21.2
discovered `mcp__agent_zero__agent_zero_delegate`, the operator returned a
structured success, and direct bridge checks confirmed empty-task and
2,000-character-limit failures are rejected before delegation. Gemma needed
three tool attempts before emitting the successful call, so the contract
passes but weak-model operator prompting remains a performance/quality
limitation. The real Agent Zero endpoint and credentials were not used.

**Decision remains: do not promote Hermes 0.21.2 yet.** Finish the bounded
operator decision and production-shaped rollback checks.
The overlay remains required for trusted per-user memory selection; native
MCP registration may make dynamic tool reconciliation removable only after
those owner-contract checks pass.
