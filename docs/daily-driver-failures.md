# Daily-driver failure log

This public-safe log records sanitized failure classes only. Owner prompts,
account identifiers, URLs, private runtime details, and personal data remain
outside the repository.

## 2026-09-14 — Recipe-authoring serving count was not exposed

- Actor: synthetic household account
- Surface: normal HADES owner API with Grocy recipe-authoring tools
- Expected: create a recipe with a resolved ingredient and verify its serving
  count against canonical Grocy
- Observed: recipe creation and one ingredient succeeded, but the installed
  owner-facing MCP schema exposed no `base_servings`/servings parameter; the
  serving-count assertion could not be performed
- Failure layer: Grocy MCP recipe-authoring contract
- Repair/evidence: added a narrow HADES-owned MCP companion that updates only
  Grocy's canonical `base_servings` field and verifies it with a follow-up
  read. A second normal HADES API turn set the synthetic recipe to two
  servings; canonical Grocy confirmed the value, then cleanup confirmed no
  fixture remained. No HADES shadow state was introduced.
- Status: REPAIRED for the API serving-count contract — the full owner-browser
  authoring sequence remains open

## 2026-09-14 — MCP adapter registration lagged the installed runtime

- Actor: HADES deployment
- Surface: Hermes private MCP server startup
- Expected: Agent Zero delegation and the Grocy recipe-serving companion
  remain available after a Hermes restart
- Observed: the installed MCP runtime rejected the older low-level adapter
  constructor and callback signatures; both adapters initially failed to
  register
- Failure layer: MCP SDK compatibility boundary
- Repair/evidence: updated both HADES-owned adapters to the installed
  low-level registration contract, restarted Hermes, and confirmed all three
  private servers registered 23 tools in total. The existing Agent Zero
  adapter and the new Grocy serving tool then registered successfully.
- Status: REPAIRED

## 2026-09-13 — Recovery helper initially targeted Grocy placeholder path

- Actor: recovery automation
- Surface: Grocy SQLite backup
- Expected: snapshot the authoritative Grocy database
- Observed: the first rehearsal targeted an empty image-level placeholder and
  produced a small structurally valid but semantically unusable artifact
- Failure layer: deployment mount-path assumption
- Repair/evidence: identified `/config/data/grocy.db` as the authoritative
  file, corrected the helper and documentation, quarantined the invalid
  rehearsal, and produced a non-empty integrity-checked artifact with
  checksums. The live Grocy database was not modified.
- Status: REPAIRED

## 2026-09-13 — Hermes API listener was bound to all interfaces

- Actor: production Hermes service
- Surface: API listener exposure
- Expected: Hermes is reachable by the containerized WebUI but not directly
  exposed on the LAN
- Observed: the profile environment bound port 8642 to `0.0.0.0`
- Failure layer: Hermes profile bind configuration
- Repair/evidence: changed the authoritative profile setting to the Docker
  host mapping used by WebUI, preserved the existing API key, restarted the
  service, confirmed WebUI-to-Hermes HTTP 200, and confirmed no loopback or
  all-interface listener remains. Runtime smoke and boundary checks pass.
- Status: REPAIRED

## 2026-09-13 — Unmanaged self-signup remained enabled

- Actor: production Open WebUI configuration
- Surface: account provisioning boundary
- Expected: new identities enter through controlled directory/admin
  provisioning
- Observed: the local self-signup option was enabled alongside production
  directory authentication
- Failure layer: Open WebUI persisted configuration
- Repair/evidence: disabled self-signup after a verified database backup;
  login, existing accounts, directory authentication, and admin provisioning
  remain available. The setting persisted across restart and runtime checks
  pass.
- Status: REPAIRED

## 2026-09-13 — Stale candidate model endpoint retried in production

- Actor: production Open WebUI runtime
- Surface: persisted model-provider configuration
- Expected: only the active Hermes provider is contacted
- Observed: a retired staging provider on port 18645 generated repeated
  connection errors after restart
- Failure layer: stale Open WebUI provider configuration
- Repair/evidence: preserved the active provider, removed only the retired
  connection after a verified database backup, restarted WebUI, and confirmed
  no new 18645 errors. HADES smoke and runtime-boundary checks pass.
- Status: REPAIRED

## 2026-09-13 — Shared household turns polluted private memory

- Actor: synthetic household account
- Surface: Hermes automatic Hindsight retention around Grocy workflows
- Expected: Grocy remains canonical shared state; ordinary grocery/pantry
  conversations do not become private semantic memories
- Observed: automatic turn retention stored shared grocery/tool-result text in
  the authenticated user's private bank, which could also pollute unrelated
  personal-memory recall
- Failure layer: Hermes Hindsight provider `sync_turn` overlay boundary
- Repair/evidence: the deployed overlay now skips automatic retention for
  shared-state turns while preserving explicit memory requests. A real
  production synthetic grocery-list request completed with no new private
  Hindsight document; an explicit synthetic memory marker was retained and
  recovered from that user's bank afterward.
- Status: REPAIRED — synthetic fixture memories remain cleanup-only test data

## 2026-09-14 — Transient external and canonical results could enter memory

- Actor: synthetic HADES domain turns
- Surface: Hermes automatic Hindsight retention around web, finance-like,
  and bounded Agent Zero requests
- Expected: transient search/operator output and live canonical finance state
  remain answer context, not durable personal memory; explicit memory requests
  remain eligible
- Observed: the existing suppression covered Grocy but did not classify these
  other non-personal domains before generic `sync_turn`
- Failure layer: Hermes Hindsight retention intent boundary
- Repair/evidence: the overlay now suppresses automatic retention and prefetch
  for web, Agent Zero, and finance-like turns unless the user explicitly asks
  to remember/recall. Static memory-boundary regression coverage verifies the
  new classifier terms; no real finance or owner memory was used.
- Status: REPAIRED — canonical systems remain authoritative and transient
  results are not promoted to personal memory by default

## 2026-09-13 — Concurrent shared Grocy mutations are slow to acknowledge

- Actor: synthetic household accounts
- Surface: two simultaneous HADES grocery mutations for the same existing
  synthetic product
- Expected: both requests converge safely on shared canonical Grocy state and
  return a usable completion result
- Observed: canonical Grocy contained exactly one unfinished shopping-list row
  after the concurrent requests, but the client-side model responses exceeded
  the bounded observation window
- Failure layer: owner-facing request latency/observability; canonical
  duplicate prevention held
- Repair/evidence: a controlled Grocy outage now suppresses personal-memory
  prefetch for ordinary live household-state questions. A synthetic outage
  retest returned only a clear Grocy connection failure, with no stale
  inventory or personal-memory claim; Grocy was restored and healthy.
- A bounded concurrent read variant returned HTTP 200 for both requests and
  each invoked the canonical stock tool once. Total latencies were 18.79s and
  22.25s; Hermes logged Grocy execution at about 0.02s per request, leaving
  local-model selection and continuation as the measured bottleneck. The
  canonical shopping list remained empty.
- A bounded simultaneous-add variant also returned HTTP 200 for both
  requests, in 24.68s and 26.86s. Both add-tool calls completed in about
  0.04s; canonical Grocy folded them into exactly one unfinished row with
  quantity 2. The verified synthetic row was then removed and canonical
  state returned to an empty list.
- Status: REPAIRED for stale-fallback behavior; concurrent response latency
  remains a separate performance investigation

## 2026-09-14 — Grocy read latency is local-model dominated

- Actor: synthetic owner API session
- Surface: read-only HADES chat asking for live Grocy shopping-list state
- Expected: query canonical Grocy and return a concise owner-facing answer
- Observed: the request completed successfully in 40.79 seconds. The first
  local-model call took 24.8 seconds, the Grocy MCP call took 0.03 seconds,
  and the post-tool model continuation took 15.8 seconds.
- Failure layer: local-model inference and post-tool continuation; Grocy and
  the MCP transport were not the bottleneck
- Repair/evidence: captured timing from the Hermes agent log without changing
  canonical state. Optimize or tune the local-model/tool continuation path
  only after comparing additional bounded read and mutation variants.
- A follow-up read with the client response ceiling set to 256 tokens completed
  in 56.23 seconds; the Grocy call still took 0.02 seconds and the model calls
  dominated. Lowering that ceiling is therefore not a validated optimization.
- Status: DIAGNOSED — no blind Grocy retry, model configuration change, or
  canonical-state mutation made

## 2026-09-14 — Web follow-up freshness passes the API contract

- Actor: synthetic HADES API session
- Surface: two-turn current-weather request with the first assistant response
  carried into the follow-up
- Expected: search the current topic on both turns and use fresh backend data
- Observed: both turns returned HTTP 200; Hermes logged SearXNG searches for
  `weather in Chicago tomorrow` and `Chicago weather Sunday` before their
  respective answers.
- Failure layer: none in the API contract; the prior stale-follow-up behavior
  did not recur
- Repair/evidence: live-web intent detection, tool narrowing, and explicit
  follow-up guidance were exercised without mutating canonical state. A fresh
  owner-UI follow-up remains the final acceptance gate.
- Status: PASS at API level; owner-UI acceptance remains pending

## 2026-09-13 — Common grocery typo bypassed live routing

- Actor: synthetic household account
- Surface: natural-language Grocy read
- Input shape: abbreviated typo (`whts on grocry rn`)
- Expected: route to live Grocy and report canonical stock
- Observed: the intent gate missed the typo and the model answered from stale
  memory context instead of querying Grocy
- Failure layer: narrow lexical intent boundary
- Repair/evidence: added common `grocy`, `grocry`, and `grocerys` variants to
  tool routing, shared-state retention suppression, and Grocy narrowing. The
  same synthetic input then returned the live canonical stock result.
- Status: REPAIRED — broader language robustness remains ongoing

## 2026-09-13 — Shorthand grocery action lacked a domain noun

- Actor: synthetic household account
- Surface: natural-language Grocy mutation
- Input shape: `add milk pls`
- Expected: route the explicit household action to Grocy and report the
  canonical mutation
- Observed: without a recognized grocery noun, the model could answer from
  prior context instead of exposing the Grocy mutation tools
- Failure layer: action-intent routing and automatic-memory boundary
- Repair/evidence: added a bounded action-plus-common-food recognizer and
  disabled automatic personal-memory prefetch for ordinary Grocy turns. The
  same synthetic input then returned a successful Grocy mutation; canonical
  Grocy showed one existing shopping-list row with its quantity updated to 2.
- Status: REPAIRED for the covered shorthand vocabulary

## 2026-09-13 — “Outta” stock shorthand bypassed Grocy

- Actor: synthetic household account
- Surface: natural-language stock question
- Input shape: `were outta milk`
- Expected: consult live Grocy before suggesting a household action
- Observed: the lexical boundary missed `outta` and the model answered from
  prior context
- Failure layer: shorthand action-intent routing
- Repair/evidence: added bounded `outta`/`out of` food-action recognition and
  applied it to model routing, Grocy tool narrowing, and memory suppression.
  The same synthetic input then returned the live Grocy stock quantity; no
  mutation was made when canonical state showed remaining stock.
- Status: REPAIRED for the covered shorthand vocabulary

## 2026-09-13 — Bare food fragment bypassed live stock lookup

- Actor: synthetic household account
- Surface: natural-language stock read
- Input shape: `milk?`
- Expected: treat a bare pantry item as a live Grocy stock lookup
- Observed: the model used prior context instead of querying the canonical
  household system
- Failure layer: fragment-intent routing and memory prefetch boundary
- Repair/evidence: added a bounded common-food fragment recognizer and applied
  it consistently to model routing, Grocy narrowing, and memory suppression.
  The same synthetic input then returned the live canonical stock quantity.
- Status: REPAIRED for the covered fragment vocabulary

## 2026-09-13 — Hindsight outage must not fall back across users

- Actor: synthetic household account
- Surface: explicit personal-memory recall during a controlled Hindsight
  outage
- Expected: fail closed without using another user's bank, owner memory, or
  guessed context
- Observed: Hindsight was unavailable during the request
- Failure layer: dependency-failure handling
- Repair/evidence: the synthetic session returned a bounded no-access answer;
  no synthetic cross-user or stale-memory marker appeared. Hindsight was
  restarted immediately and its canonical health endpoint returned healthy.
- Status: PASS — no code change required

## 2026-09-13 — Web outage appended unrelated household context

- Actor: synthetic household account
- Surface: web-search failure response
- Expected: report the unavailable search source without presenting unrelated
  personal or live-household claims
- Observed: SearXNG failure was reported correctly, but stale Grocy/memory
  context was appended to the response
- Failure layer: automatic-memory prefetch on pure web turns
- Repair/evidence: pure web turns now disable automatic personal-memory
  prefetch at the agent boundary while explicit memory composition remains
  available. A repeated synthetic SearXNG outage returned only the connection
  failure and no unrelated household marker; SearXNG was restored afterward.
- Status: REPAIRED

## 2026-09-13 — Identity-provider outage fails closed

- Actor: synthetic household account
- Surface: fresh directory login during a controlled production LLDAP outage
- Expected: authentication fails without guessing a subject or expanding
  privileges
- Observed: the LDAP login returned HTTP 400 and no bearer token
- Failure layer: identity-provider availability
- Repair/evidence: LLDAP was restored and its health endpoint recovered. The
  owner account was not probed or changed during this test.
- Status: PASS — local owner fallback remains a separate preserved path

## 2026-09-13 — Built-in theme selection resurrects an old HADES preset

- Actor: owner account
- Surface: Open WebUI theme settings and reload
- Expected: choosing a native Open WebUI theme clears any HADES preset for
  that account and remains selected after refresh
- Observed: an account-level Odysseus preset returned after refresh because
  the native-theme branch removed only browser state and never cleared the
  stored HADES preference
- Failure layer: HADES theme preference persistence
- Repair/evidence: the native-theme branch now clears both browser and
  account-scoped HADES preference; a valid account response with no HADES
  preset also removes stale browser state. Preference fallback storage is now
  namespaced by the authenticated Open WebUI subject, preventing one account
  from inheriting another account's local preset. Legacy unscoped keys are
  removed when the authenticated subject is established. The deployed asset
  cache version was advanced so existing browsers fetch the repair.
- Status: REPAIRED — owner should select the desired native theme once after
  a hard refresh; no owner preference was changed automatically

## 2026-09-13 — Directory revocation does not revoke WebUI bearer sessions

- Actor: synthetic household account
- Surface: staged LLDAP + Open WebUI authentication
- Expected: removing a directory identity prevents both new and existing
  application sessions from authenticating
- Observed: new LDAP login failed after directory deletion, but a previously
  issued Open WebUI token still authorized requests
- Failure layer: application session lifecycle; Open WebUI validates token
  signature and local user existence, not live directory membership
- Repair/evidence: supported Open WebUI user deletion invalidated the old token
  with HTTP 401. The ordered bridge is the accepted procedure; it now also
  continues safely when a prior interrupted run already removed the
  application account. Automatic directory-to-application event sync remains
  a separate future architecture decision.
- Status: PASS operationally — coordinated revocation is deterministic; event
  synchronization is intentionally not implemented
