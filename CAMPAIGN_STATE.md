# HADES Campaign State

This public-safe checkpoint records project direction, not deployment state.
Private runtime details, credentials, accounts, hostnames, addresses, chat
history, and owner data belong in the deployment environment and are never
recorded here.

## CURRENT CAMPAIGN CHECKPOINT

Household Alpha is accepted as complete/ready. Real household onboarding is
an owner-input gate only and is not a reason to pause independent engineering
work. Hermes 0.21.2 promotion was attempted and rolled back after owner
authentication could not be proven; production remains on the known-good
Hermes 0.14.0 baseline.

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
- Approve one concrete deterministic automation workflow, its actor/capability
  mapping, canonical system, confirmation rule, and failure/rollback behavior;
  the preparation contract is in `docs/automation-boundary.md`.

## INDEPENDENT PROGRESS

- Deterministic automation preparation is complete without provisioning a
  runner or granting new authority. The proposed boundary requires trusted
  subject/capability resolution, explicit preview/apply semantics,
  idempotency, canonical verification, and fail-closed unknown outcomes.

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
  production Household Alpha is ready; real household onboarding is separately
  owner-gated.

Continue independent roadmap work. The current highest-value item is Hermes
0.21.2 production-readiness; production remains on the known-good 0.14.0
baseline until the owner-preserving candidate rehearsal passes.

Synthetic production dogfood found that Hermes' automatic Hindsight `sync_turn`
path retained ordinary Grocy/shared-state turns in a user's private semantic
memory, polluting later personal recall. The deployed overlay now skips that
automatic retain path for shared-state turns while preserving explicit memory
requests. A real synthetic grocery-list request produced no new private
Hindsight document, and an explicit synthetic memory marker was retained and
recalled. Static regression coverage and Python compilation pass; owner data
was not inspected or changed.

The latest Hermes 0.21.2 isolated probe passed normal chat and native stdio
MCP discovery/call/post-tool continuation with local `gemma4:12b`. Qwen 3 8B
and 14B are below the candidate's enforced 64K context floor, so they are not
candidate production profiles. The isolated Hindsight, Grocy, SearXNG,
bounded Agent Zero bridge, synthetic Actual Budget, disposable Open WebUI,
and rollback checks are recorded. The owner-preserving rehearsal against a
disposable copy of existing WebUI state passed: the original Luna account
ID/role and existing chat history rendered through candidate Hermes, and a
candidate chat persisted in the clone. Production Hindsight read-only checks
confirmed the existing owner bank and zero pending operations; the candidate
overlay maps the actual owner subject to owner scope and malformed subjects to
denied scope. The isolated matrix is promotion-ready for a controlled,
rollback-backed change window. No production upgrade has been executed;
production remains on Hermes 0.14.0. A fresh private preflight backup set has
now been created and checksum-validated; it supersedes the older incomplete
backup artifacts for any future change window.

A controlled production promotion was attempted after this staging decision.
Hermes 0.21.2 reached health with the retained overlay and Gemma 12B, but the
owner regression could not authenticate using the available protected
bootstrap credential. Per rollback policy, the original unit/profile were
restored and Hermes 0.14.0 was explicitly restarted; production WebUI and
Hermes are healthy again. No application database or owner identity changed.
The production decision is DEFERRED, not accepted. A retry requires a verified
current owner authentication/session path before burn-in.
The promotion-critical candidate subset passes 166/166 through HADES'
hardened canonical-runner wrapper with the candidate interpreter. A full-suite
run still exposes one upstream process-global
auxiliary-provider leak; the repository includes a correct-interpreter check
and isolated-worker qualification path. A direct per-file-runner experiment
completed 3,986 files with 27,353 passed and 222 platform skips, but bypassed
the candidate's canonical `scripts/run_tests.sh` hermetic wrapper. Its shared
virtualenv was mutated by update/venv tests, producing later `No module named
pytest` errors; that aggregate is not qualification evidence. Candidate triage
also includes a timing-sensitive compression fallback failure and four
reported flakes. A valid full run requires the canonical wrapper with a fresh
candidate environment.
The disposable candidate environment was subsequently restored with
`ensurepip` and test dependencies; the canonical wrapper passed a focused
three-file contract run with 134/134 tests. This does not qualify the full
suite. The focused follow-up also passed the compression-stall file. The
canonical wrapper also passed the four updater/venv-repair files serially
(118 passed, one host-gated skip), with pytest still importable afterward.
This narrows the environment damage to the broader full-suite interaction;
full qualification remains pending.
The two local-quickstart fixture failures were then repaired in the disposable
candidate checkout by supplying a synthetic planning budget; its complete
file passed 7/7 through the canonical wrapper and pytest remained intact.
That focused blocker is removed, while full-suite qualification and upstream
disposition remain pending.
The affected memory-provider files subsequently passed together under two
canonical workers (112 passed, 0 failed), with pytest still importable. This
is focused evidence for the cleanup fixture, not full-suite qualification.

## HOUSEHOLD ALPHA STATUS

The detailed bullets below retain historical evidence from staging and
migration work. The current private production checkpoint supersedes any
older `PARTIAL` labels: Household Alpha is COMPLETE / READY. Real household
onboarding is the only owner-input gate; it does not pause independent work.

- Owner daily-driver path: PASS; production smoke remains green.
- Identity provider: PASS for the accepted production Household Alpha
  checkpoint; private deployment details remain in the deployment record.
- Stable subjects: PASS in the accepted production Household Alpha checkpoint.
- Subject propagation: PASS in the accepted production Household Alpha
  checkpoint; Hermes 0.21.2 candidate scope regression is also recorded.
- Conversation isolation: PASS + PERSISTENCE in isolated staging; Alpha and
  Beta cannot list or directly open one another's chats, including after
  LLDAP and WebUI restart.
- Clean owner/household fixture: PASS + PERSISTENCE. A synthetic owner is the
  staging admin while Alpha and Beta are ordinary users; each retained its
  subject, role, and private chat across WebUI restart and fresh LDAP login.
- Memory isolation: PASS + PERSISTENCE in the accepted production Household
  Alpha checkpoint; the existing owner bank remains mapped privately.
- Hermes subject-aware memory path: PASS + PERSISTENCE in disposable
  end-to-end staging; Alpha/Beta retained and recalled separate synthetic
  facts, including an adversarial cross-user request. A prior static-bank
  failure was corrected by placing `bank_id_template` in the provider's
  authoritative JSON configuration.
- Shared Grocy: PASS + PERSISTENCE in disposable end-to-end staging; Alpha
  added synthetic Milk through Hermes/MCP, Beta saw the same canonical shared
  list, and the item remained after Grocy/Hermes restart. Production Grocy
  was not touched.
- Synthetic revocation: PASS in the accepted production Household Alpha
  checkpoint; the operational session-invalidation semantics are documented.
- User-specific settings: PASS + PERSISTENCE in isolated staging. Alpha and
  Beta retained different settings across Open WebUI restart and re-login.
  Newly provisioned LDAP users require supported promotion from `pending` to
  `user` before normal settings access.
- Household finance isolation: PASS in the accepted production Household Alpha
  checkpoint; real finance remains separately owner-gated.
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
- Household Alpha readiness report: the current private production checkpoint
  declares Household Alpha complete/ready; first real household onboarding is
  owner-gated. Rendered revocation and Grocy mutation/cross-user read
  acceptance remain recorded as supporting evidence.
- Shared Grocy is PASS + PERSISTENCE in disposable end-to-end staging;
  finance exclusion is PASS for server-marked disposable household sessions.
- Agent Zero household policy: owner-only in production; the candidate
  contract uses a bounded synthetic bridge and does not grant household
  Agent Zero access.
- Recovery: current owner/admin fallback and the fresh private Hermes
  preflight backup set are preserved; older incomplete artifacts are not
  rollback inputs.
- Current private recovery checkpoint: fresh Open WebUI, Grocy, LLDAP, and
  Hermes SQLite snapshots pass integrity checks; matching profile assets,
  encrypted off-host retention, isolated restore, and native Hindsight export
  remain unproven.
- Synthetic identity recovery: PASS in the accepted production checkpoint.
- Next highest-value action: keep production on Hermes 0.14.0 while the owner
  authentication path and candidate full-suite isolation gate are resolved;
  then execute the separately controlled Hermes 0.21.2 production change
  window. The preserved rollback set remains authoritative.
