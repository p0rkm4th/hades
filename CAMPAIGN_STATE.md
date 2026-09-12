# HADES Campaign State

This public-safe checkpoint records project direction, not deployment state.
Private runtime details, credentials, accounts, hostnames, addresses, chat
history, and owner data belong in the deployment environment and are never
recorded here.

## CURRENT OBJECTIVE

Build an owner-usable HADES composition from mature upstream systems while
preserving source-of-truth boundaries and least privilege.

## CURRENT HEAD

`2bc6f58794b8acdf06414b32466dc304cea8ab71` — synthetic finance bakeoff
 checkpoint committed and pushed. Actual Budget is provisional SELECT WITH
 CONDITIONS; its official API client authenticated against staging but could
 not load the downloaded budget because the client migration set is behind the
 staged server budget (`out-of-sync-migrations`).

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
- The Actual Budget API compatibility gate is open: the published
  `@actual-app/api` client can authenticate and enumerate synthetic budgets, but
  loading one fails with `out-of-sync-migrations` against the tested server
  image. Do not promote Actual or connect real finance data until matching
  client/server revisions or a safer supported read path are proven.

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

## CAPABILITY LEDGER

See `docs/CAPABILITY_LEDGER.md` for the sanitized verified capability state.

## NEXT ACTION

Obtain explicit owner authorization for exact homelab endpoints and
least-privilege credentials, then provision only read-only Proxmox, NetBox, or
Uptime Kuma access and verify it through the HADES owner path. Credential-
independent preparation is documented in `docs/homelab-readonly.md`. Finance
preparation is complete in `docs/finance-readonly.md`; provider, account,
environment, retention, and webhook authorization remain owner-gated.

Hermes production remains pinned while an isolated external-contract staging
matrix is unavailable. The next non-gated engineering action is a disposable
staging deployment with synthetic domain services, followed by owner-path
contract verification and rollback rehearsal.

The synthetic finance bakeoff is SELECT WITH CONDITIONS for Actual Budget,
with Firefly III as fallback and Finlynq/Ledgr on watchlist. Evidence and the
remaining synthetic HADES adapter conditions are in
`docs/adr/finance-platform.md`.

The next finance action is to resolve the Actual client/server migration
compatibility in disposable staging, then rerun synthetic import, read, reload,
restart, and restore acceptance before any HADES adapter is added.

Shared LDAP identity is staged in `docs/shared-identity.md` but intentionally
deferred until the multi-user roadmap milestone is complete.

Browser automation is now provisioned in an isolated temporary environment
and reaches the HADES login shell at both local and Tailscale URLs in desktop
and mobile viewports. An authenticated synthetic dogfood session verified the
native mobile Settings flow: Language precedes Theme, all HADES theme/effect
selectors render, an Odysseus theme plus Rain creates the expected canvas and
classes, and both selections persist after reload. No owner credentials were
stored by the dogfood run; domain workflow browser evidence remains pending.
