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
- A real disposable Agent Zero runtime has not been attached; production
  endpoints and credentials remain deliberately excluded from candidate
  testing. The synthetic SearXNG endpoint and bounded bridge fixture were
  validated separately below.

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

The isolated candidate matrix is materially green. Synthetic Actual Budget
and a fresh disposable Open WebUI owner-facing path have passed. The
owner-state rehearsal proved account/chat continuity and candidate UI
operation without connecting candidate code to production Hindsight. A
read-only production Hindsight check confirmed the existing `hades-owner`
bank is present with zero pending operations, and the candidate overlay maps
the actual private owner subject to owner scope while malformed subjects remain
denied. This establishes the history-preserving mapping invariant without
exposing owner memories to the candidate.

The full isolated candidate contract is promotion-ready for a controlled
change window. A real Agent Zero runtime is not required for the candidate:
the bounded bridge passed with a loopback fixture, while the separately
booted real image rejected an unavailable synthetic credential with HTTP 401.
Native A2A/real-runtime credential provisioning remains a separate follow-up.
Production remains on Hermes 0.14.0; no production upgrade has been executed.

The candidate runtime also passed the subject-scope regression: the trusted
owner subject maps to owner scope, a household subject maps to household
scope, and empty, malformed, or untrusted keys map to denied scope. This
prevents a malformed identity from inheriting household tools. The check was
run with the Hermes 0.21.2 candidate interpreter and the repository overlay.

## Supported full-suite qualification attempt

On 2026-09-13, the candidate's documented per-file process-isolated runner
completed its first full Linux attempt: 3,986 files were discovered, 27,353
tests passed, 222 were skipped for platform gating, and three test failures
were counted after the runner's retry policy. Four additional files were
reported as flaky, and multiple later files collected no tests after the
shared virtualenv lost `pytest`. The run is not a promotion pass.

The run exposed an environment-isolation defect in the qualification setup:
the runner gives each pytest subprocess a fresh interpreter and temporary
pytest root, but all workers share the candidate virtualenv filesystem. Tests
that exercise update/venv behavior removed `pytest` from that shared virtualenv
while other files were still being scheduled; subsequent files then failed
with `No module named pytest`. A clean qualification must use an immutable
candidate environment per worker (or a disposable environment snapshot), and
must not count environment-mutating tests as ordinary promotion evidence.

The first substantive failures also included a timing-sensitive compression
stall-fallback assertion and local quickstart assertions returning HTTP 409
instead of the expected 200. These require separate upstream triage after a
clean environment is available. Production remains on Hermes 0.14.0.

## Upstream-only comparison

A separate loopback Hermes 0.21.2 launch was run without the repository
overlay. Ordinary completion succeeded, and upstream Hermes registered the
configured native MCP servers and their tools. With default auxiliary and
tool-search settings, a bounded owner-style Grocy turn repeatedly entered
tool-search/title-generation work and exceeded the probe window. The same
upstream-only candidate was then rerun with supported configuration disabling
title generation and tool search; native Grocy completed in one tool turn and
returned the expected marker. Base chat, MCP registration, and the configured
Grocy path are therefore upstream capabilities.

The overlay therefore remains intentionally narrow rather than being copied
blindly or removed wholesale. Its subject validation/capability filtering,
HADES-specific model and web routing, Hindsight reconciliation/streaming
handling, and owner-facing reliability behavior still require the overlay.
Grocy reconciliation can be disabled for the modern candidate when the
supported native-MCP configuration is used, but it remains required by the
production 0.14.0 path until that service is migrated and its full owner
contract is retested. The upstream-only probe also reported Hermes' linked
SQLite runtime warning and a stale systemd timeout warning; these are candidate
change-window hardening items, not production changes.

The upstream-only memory comparison is a security boundary: with a trusted
synthetic session key and the configured `bank_id_template`, Hermes 0.21.2
initialized the base synthetic bank rather than the subject-specific bank.
The request completed, but the bank selection was not isolated. The HADES
subject-to-bank mapping overlay must therefore be retained until upstream
provides an equivalent server-side mapping and it passes the two-user
isolation contract.

The candidate launch also requires a clean process working directory. Starting
from the Hermes source checkout injects its large `AGENTS.md` into API prompts;
starting from an empty workspace with `terminal.cwd` configured avoids that
source-tree prompt contamination. The owner-facing change-window unit must
use the clean-workspace pattern.

The candidate also exposed a deployment-context requirement. Starting the
gateway from the Hermes source checkout caused the checkout's `AGENTS.md` to
be injected into API prompts, including a truncation warning and contaminated
model output. Starting the same candidate from an empty working directory,
with `terminal.cwd` set to that workspace and the source supplied only through
the runtime path, removed the contamination; the overlay-backed memory turn
then completed normally. A production unit must therefore use a clean
working directory and must not use the Hermes source checkout as its prompt
context.

The matched synthetic Actual Budget 26.9.0 fixture was then started on an
isolated port. Hermes 0.21.2 discovered all three migrated read-only finance
tools; a candidate `finance_status` call returned the synthetic budget,
server version, and `read_only: true`. Direct bridge calls also returned
synthetic accounts and transactions. The fixture was stopped afterward.

Finally, a fresh disposable Open WebUI instance with its own volume was
pointed at the candidate. Synthetic signup/login succeeded, the WebUI model
catalog exposed `gemma4:12b`, and the WebUI chat-completions path returned the
exact marker `UI-CANDIDATE-READY`. The disposable WebUI and candidate were
removed afterward; the existing staging WebUI and production WebUI were not
retargeted.
The overlay remains required for trusted per-user memory selection; native
MCP registration may make dynamic tool reconciliation removable only after
those owner-contract checks pass.

## Owner-state migration rehearsal

On 2026-09-13, the production WebUI data directory was copied into a
mode-0700 disposable clone after SQLite integrity validation. The clone
contained the existing account and chat set without changing the source. A
supervised Hermes 0.21.2 gateway was then bound to loopback port 8643 and the
clone was run on port 3021 with the candidate model endpoint. The preserved
Luna account authenticated with its original account ID and admin role; the
existing chat titles were visible in the rendered UI; a prompt returned the
exact `DOM-CANDIDATE-OWNER-READY` marker; the resulting marker was present in
the cloned WebUI database; and the candidate model was visible through the
UI/API path. The clone container, copied data, candidate gateway, and
temporary credential were removed afterward. Production WebUI and Hermes
0.14.0 remained healthy throughout.

This proves the owner-facing identity/chat continuity path against a
disposable WebUI-state copy. It does not prove production Hindsight history
mapping or a real Agent Zero runtime, so it is not authorization to promote
the candidate by itself.

## Disposable real Agent Zero check

The pinned Agent Zero image was started separately with a fresh named volume
and loopback-only port. It booted its real UI/API stack successfully, but its
protected `/api/api_message` endpoint rejected the synthetic bridge key with
HTTP 401. The image generates/manages its MCP API token inside its own
settings; no safe staging credential was available without creating an
additional authenticated setup flow. The candidate container and volume were
removed. Production Agent Zero and its credentials were not used. The
existing bounded MCP bridge remains the approved candidate contract, while
native A2A and real-runtime credential provisioning remain separate work.

## Focused candidate regression run

On 2026-09-13, the installed Hermes 0.21.2 candidate suite ran 166 focused
tests covering memory-provider behavior and unavailable-memory warnings,
conversation scope, MCP discovery and transport, gateway authentication, and
identity-token resolution. All 166 passed. This is additional candidate
evidence only; production remains on Hermes 0.14.0 pending the owner-authenticated
promotion rehearsal.

## Full-suite qualification note

A full candidate-suite run on 2026-09-13, invoked through the candidate
interpreter with `python -m pytest`, reached 846 passed, 20 skipped, and 53
deselected before stopping at one failure in
`TestGetTextAuxiliaryClient.test_returns_none_when_nothing_available`. The
test passes alone and the complete `test_auxiliary_client.py` file passes
(204/204), so the failure is order-dependent: an earlier test leaves the
candidate's process-global main-provider state set to a test OpenRouter
provider. This is upstream test isolation debt, not a production HADES
failure. The initial launcher-based run also reported four Anthropic-provider
failures because that launcher targeted an older staging virtualenv; those
were eliminated by using the candidate interpreter directly. The full suite
should still be clean or run in isolated workers before calling the candidate
fully promotion-qualified.

HADES provides [`scripts/test-hermes-candidate.sh`](../scripts/test-hermes-candidate.sh)
for the promotion-critical subset. It requires a candidate directory and uses
that directory's `.venv/bin/python -m pytest`, preventing a stale cloned
`pytest` launcher from selecting a different staging environment.

### Minimal upstream remediation

The failing row-addressed-backfill module should own an autouse fixture that
clears the auxiliary runtime state before and after each test, or the shared
helper should be moved into a fixture module whose scope covers that test. The
fixture must call the upstream `clear_runtime_main()` cleanup path; changing
the assertion or disabling the test would conceal the leak. Acceptance is a
clean full-suite run with the candidate interpreter and no cross-test provider
state, followed by the focused HADES candidate check.
