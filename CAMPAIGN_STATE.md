# HADES Campaign State

This public-safe checkpoint records project direction, not deployment state.
Private runtime details, credentials, accounts, hostnames, addresses, chat
history, and owner data belong in the deployment environment and are never
recorded here.

## CURRENT CAMPAIGN CHECKPOINT

Household Alpha is accepted as complete/ready. Real household onboarding is
an owner-input gate only and is not a reason to pause independent engineering
work. The active independent work is Hermes 0.21.2 production-readiness
staging; production remains on the known-good Hermes 0.14.0 baseline.

## CURRENT OBJECTIVE

Build an owner-usable HADES composition from mature upstream systems while
preserving source-of-truth boundaries and least privilege.

## CURRENT HEAD

`sanitized-history release checkpoint` — the reachable `main` history has been sanitized for public release;
the current tree and full-history audit contain no owner identifiers, tailnet
hostnames, private network literals, or credential-like tracked paths. Account-
scoped theme preferences, recovery evidence, and the supported Open WebUI
theme-handling fixes remain committed. A complete pre-rewrite bundle is held
outside the repository for rollback if needed.
Founding capabilities and
current upstream/A2A decisions are reconciled; Actual remains selected for
synthetic HADES integration and production finance is gated.

## COMPLETED MILESTONES

- Established an independent HADES repository and composition doctrine.
- Evaluated Hermes, Open WebUI, Hindsight, Grocy, Agent Zero, and read-only
  homelab/finance integration surfaces.
- Added Open WebUI theme/effect extension assets without creating a frontend
  fork or a HADES-native agent core.
- Documented adaptive model capability behavior: tool-capable models may use
  HADES integrations; completion-only models must be clearly identified and
  must not receive tool payloads.

## OWNER-VERIFIED WORKFLOWS

Private deployment acceptance is maintained outside this public repository.
The public acceptance file contains only workflow definitions and evidence
requirements.

## CURRENT DEPLOYED COMPONENTS / VERSIONS

Deployment-specific versions, image digests, endpoints, and model choices are
intentionally maintained in private operations state.

## CLOSED FOUNDING INTEGRATIONS / FUTURE HARDENING

- Agent Zero is deployed privately with a dedicated volume and pinned image;
  its standalone UI/model smoke path passes. A one-tool private MCP adapter is
  now connected, correctly surfaces upstream failure, and has returned a clean
  bounded success through the HADES owner API. A fresh synthetic mobile HADES
  chat rendered the bounded Agent Zero result in the assistant DOM after tool
  completion. This closes the founding bounded-delegation milestone;
  persistent delegated context and broader operator tasks remain future work.
- Grocy is deployed privately with a dedicated persistent volume and pinned
  image; its HTTP path passes. The HADES API owner path now successfully calls
  the canonical stock and shopping-list tools against synthetic data. Add,
  remove, and correction/re-add turns have been verified against Grocy's
  canonical shopping-list API; an earlier mutation survived a Grocy restart
  and was recovered by a fresh HADES query. A fresh synthetic mobile browser
  session rendered a read-only stock answer through normal HADES chat and it
  matched Grocy's canonical stock. A fresh synthetic mobile mutation added milk
  through HADES; Grocy showed one unfinished row at quantity two, and the chat
  result survived reload. This closes the founding Grocy milestone; additional
  pantry edge cases and local-model wording remain future hardening.
  A context-loss defect was found when “remove it” was treated as a generic
  task-list request; the deployed overlay now carries recent conversation
  context into Grocy intent detection. The same follow-up removed the item,
  survived reload, and left the canonical shopping list empty.
  A mobile recipe-availability turn also rendered the makeable result; Grocy's
  canonical recipe and stock records matched the two-unit requirement, and the
  result survived reload.
  Repeated-add duplication was found, fixed in the
  active MCP deployment, and regression-tested as quantity folding. The
  bounded stock-intake preview plus explicitly confirmed apply path now also
  passes against canonical Grocy stock; the local model still needs explicit
  workflow wording for apply turns. A canonical consume turn was added to the
  private allowlist and verified by reducing synthetic stock from 3 to 2.
  Recipe fulfillment had a version-field bug; the private adapter now uses
  Grocy's stable missing-product count. Both available and one-unit-short
  branches were verified, and the synthetic fixture was restored.
  Recipe add-missing also had a content-type defect; the private client now
  sends the required JSON body. Its shortage workflow was verified to merge
  into the existing shopping row without duplication.
  A controlled Grocy plus Hermes restart preserved the recipe, stock, and
  shopping-list fixture, and a fresh owner query recovered the canonical row.

- A synthetic recipe-fixture fact was retained and recalled through HADES, then
  combined with live Grocy fulfillment. A fresh synthetic mobile chat verifies
  the single-turn browser path: Hindsight recalled the remembered label and
  Grocy checked live stock and fulfillment in the same turn. A correction turn
  changed the remembered label while the canonical Grocy recipe remained
  unchanged and makeable; a fresh mobile correction query also returned the
  corrected label rather than the stale paraphrase. The composition result
  survived reload. This closes the founding memory-plus-household composition
  milestone.

## REAL OWNER GATES

- Real Finance/Plaid account authorization is owner-gated.
- Existing Proxmox, NetBox, Uptime Kuma, or Home Assistant credentials are
  owner-gated if those systems are to be connected.
- Destructive infrastructure authority and new privileged host access remain
  prohibited without explicit authorization.

## PENDING OWNER GATES

- Authorize and provision each external integration independently.
- Capture owner-UI plus canonical-system verification in private acceptance
  records before enabling writes.

## ARCHITECTURAL DISCOVERIES

- Existing mature systems remain preferred over new HADES subsystems.
- Hindsight supplies context, not canonical household, finance, or homelab
  state.
- Agent Zero is a bounded subordinate operator, not a second HADES brain.
- Ambiguous data-bearing artifacts must be preserved until their ownership is
  known.

## OPEN DEFECTS

- Single-turn memory-plus-Grocy composition is now narrowed to the relevant
  read tools and verified through the owner UI; unrelated household tools stay
  out of that mixed request.
- The Actual API client/server compatibility gate is resolved for the selected
  pinned 26.9.0 pair. The earlier `out-of-sync-migrations` result remains
  historical evidence for why matching pins are required; the stable pair
  passed import, repeat reconciliation, reload, transfer linking, and the
  constrained owner read path. Real finance remains owner-gated.

## HERMES OVERLAY STATUS

- The deployment compatibility overlay is source-represented at
  `hermes/sitecustomize.py` and remains intentionally narrow.
- It handles local model routing, Hindsight retain/recall normalization,
  explicit-memory tool narrowing, streaming handoff, and related weak-model
  compatibility behavior.
- It is not a HADES runtime, planner, router framework, or new core.
- Every retained behavior now has a stated upstream gap, evidence requirement,
  and removal condition in `docs/hermes-overlay-inventory.md`.

## PUBLIC CI STATUS

- A minimal secret-free GitHub Actions tripwire compiles the public adapters,
  runs the memory and public-history checks, and validates shell syntax.
- It does not replace private owner-UI, canonical-domain, or runtime
  acceptance.

The current tree and reachable public history contain no private network
literal; the smoke probe discovers the model gateway dynamically. The remote
history rewrite is an explicit release action and does not alter the deployed
runtime.

## CAPABILITY LEDGER

See `docs/CAPABILITY_LEDGER.md` for the sanitized verified capability state.

## NEXT ACTION

Household Alpha is complete/ready in the current production checkpoint:
identity mapping, conversation and memory isolation, shared Grocy,
capability exclusion, per-user settings, revocation, restart, and recovery
evidence are recorded in the private migration state. Real household
onboarding remains an owner-input gate only.

Keep production Hermes on its known-good baseline and local Open WebUI
authentication fallback enabled. A private production migration checkpoint now
has validated backups/rollback, a recovered dedicated admin, private LLDAP,
exact owner mapping, and synthetic production identities. Mobile browser-DOM evidence now
covers rendered login, private-chat sidebar isolation, household model
visibility, memory retain/recall, shared Grocy read/mutation and cross-user
read, finance exclusion, revocation, and cross-account settings isolation;
  additional Grocy purchase/consume variations remain optional hardening. The
  production migration is still in acceptance, not declared Household Alpha.

Continue independent roadmap work. The current highest-value item is Hermes
0.21.2 production-readiness; production remains on the known-good 0.14.0
baseline until the owner-preserving candidate rehearsal passes.

The latest Hermes 0.21.2 isolated probe passed normal chat and native stdio
MCP discovery/call/post-tool continuation with local `gemma4:12b`. Qwen 3 8B
and 14B are below the candidate's enforced 64K context floor, so they are not
candidate production profiles. The isolated Hindsight, Grocy, SearXNG,
bounded Agent Zero bridge, synthetic Actual Budget, disposable Open WebUI,
and rollback checks are recorded. Remaining gates are the owner-preserving
migration rehearsal against a disposable copy of existing WebUI state and the
final disposition of real Agent Zero runtime validation; production remains on
Hermes 0.14.0.

## HOUSEHOLD ALPHA STATUS

The detailed bullets below retain historical evidence from staging and
migration work. The current private production checkpoint supersedes any
older `PARTIAL` labels: Household Alpha is COMPLETE / READY. Real household
onboarding is the only owner-input gate; it does not pause independent work.

- Owner daily-driver path: PASS; production smoke remains green.
- Identity provider: PARTIAL; a separate pinned production LLDAP is healthy,
  persistent, private, and grouped. Directory-backed Open WebUI
  authentication is enabled with local owner fallback preserved.
- Stable subjects: PARTIAL; synthetic Alpha/Beta subjects are distinct and
  stable across repeated LDAP login in disposable Open WebUI staging.
- Subject propagation: PARTIAL; disposable staging proved the server-side
  `{{USER_ID}}` and group expansion, and production now stores those templates
  on the existing Hermes connection. Runtime owner verification remains.
- Conversation isolation: PASS + PERSISTENCE in isolated staging; Alpha and
  Beta cannot list or directly open one another's chats, including after
  LLDAP and WebUI restart.
- Clean owner/household fixture: PASS + PERSISTENCE. A synthetic owner is the
  staging admin while Alpha and Beta are ordinary users; each retained its
  subject, role, and private chat across WebUI restart and fresh LDAP login.
- Memory isolation: PASS + PERSISTENCE in isolated Hindsight staging; Alpha
  and Beta banks remain separate across Hindsight restart. Production owner
  mapping remains the existing bank and is being verified through the owner
  path.
- Hermes subject-aware memory path: PASS + PERSISTENCE in disposable
  end-to-end staging; Alpha/Beta retained and recalled separate synthetic
  facts, including an adversarial cross-user request. A prior static-bank
  failure was corrected by placing `bank_id_template` in the provider's
  authoritative JSON configuration.
- Shared Grocy: PASS + PERSISTENCE in disposable end-to-end staging; Alpha
  added synthetic Milk through Hermes/MCP, Beta saw the same canonical shared
  list, and the item remained after Grocy/Hermes restart. Production Grocy
  was not touched.
- Synthetic revocation: PARTIAL. LLDAP deletion blocked new Beta login, but
  an already-issued Open WebUI token remained valid until the corresponding
  Open WebUI user was deleted through its supported admin endpoint. The narrow
  ordered bridge in `scripts/revoke-directory-user.sh` now closes existing
  sessions before directory deletion and verifies both stores; automatic
  directory event synchronization remains a future architecture gate.
  Production identity is unchanged.
- User-specific settings: PASS + PERSISTENCE in isolated staging. Alpha and
  Beta retained different settings across Open WebUI restart and re-login.
  Newly provisioned LDAP users require supported promotion from `pending` to
  `user` before normal settings access.
- Household finance isolation: PARTIAL at the production overlay boundary;
  production finance is absent, but per-user capability propagation is not
  enabled.
- Disposable capability exclusion: PASS. Server-marked Alpha/Beta sessions
  received neither Agent Zero nor finance tools and returned no financial
  value under adversarial requests.
- Directory group propagation: PASS in disposable staging. With supported LDAP
  group management enabled, synthetic Alpha and Beta synchronized into the
  intended household groups, and a downstream echo received both the stable
  subject and expanded group headers. Production remains unchanged.
- WebUI model visibility and end-to-end subject memory: PASS + PERSISTENCE in
  disposable staging. A supported household-group model access grant exposed
  Hermes to both ordinary users; each retained and recalled only its own fact
  through WebUI → Hermes → Hindsight. The disposable provider was removed
  afterward. A later corrected mobile DOM run re-confirmed the rendered model
  selector, memory retain, fresh-chat recall, and subject-specific Hindsight
  bank selection. The same run rendered the shared Grocy list and its
  canonical rows matched; a finance probe rendered an explicit no-access
  response with no private value. A faster Dolphin profile was unsuitable
  for recall/tool acceptance, so the disposable run used the known
  tool-capable Qwen profile. All temporary providers and gateways were
  removed afterward.
- Household Alpha readiness report: staging contract is substantially green,
  but production declaration is intentionally pending the owner-preserving
  identity migration gate. Rendered revocation and Grocy mutation/cross-user
  read acceptance now pass in disposable staging.
- Shared Grocy is PASS + PERSISTENCE in disposable end-to-end staging;
  finance exclusion is PASS for server-marked disposable household sessions.
- Agent Zero household policy: owner-only in the current unmarked production
  session; the overlay now fail-closes Agent Zero for server-marked household
  sessions, but the Open WebUI scope header is not yet configured.
- Recovery: existing owner recovery path preserved; identity backup mapping
  still requires a private operational rehearsal.
- Synthetic identity recovery: PASS. A quiesced LLDAP staging database passed
  SQLite integrity validation and booted successfully in a separate pinned
  restore container. Production owner recovery and automatic application
  subject remapping remain unproven.
- Next highest-value action: keep staging clean and complete rendered
  revocation plus Grocy mutation/cross-user acceptance if useful; otherwise
  prepare the owner-preserving production identity migration rehearsal with
  private backups and rollback targets. Do not touch production without that
  owner gate.
