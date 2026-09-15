# HADES stable-v1 readiness

This is a readiness record for the current deployment, not an installer or a
new runtime layer. Production remains on the known-good Hermes 0.14.0 path
while the Hermes 0.21.2 promotion branch is parked on owner authentication.

## Current component contract

| Component | Production role | Current state | Canonical authority |
|---|---|---|---|
| Open WebUI | owner-facing conversation surface | pinned 0.11.1 deployment | conversations, users, settings |
| Hermes | agent execution and tool lifecycle | 0.14.0, healthy | turn execution and tool results |
| Hindsight | durable personal context | healthy, subject-scoped overlay | private semantic memory |
| Grocy | household pantry and grocery state | healthy, shared | inventory, shopping, recipes |
| SearXNG | web search | healthy, private | search results and freshness |
| Agent Zero | bounded subordinate operator | healthy, owner-scoped | delegated task evidence |
| LLDAP | staged/production identity foundation | private and persistent | directory identity and groups |

Hermes' production API listener is bound to the Docker host mapping used by
the containerized WebUI, rather than all host interfaces; the WebUI remains
LAN-reachable while Hermes itself is not directly LAN-exposed.

## Non-negotiable boundaries

- Hindsight supplies context; it does not replace live Grocy, finance,
  homelab, or smart-home truth.
- Ordinary shared-state turns do not enter private Hindsight automatically.
  Explicit memory requests remain user-scoped.
- Household capability filtering occurs before model invocation; finance and
  Agent Zero are not household capabilities.
- Missing identity or capability resolution fails closed. Model text cannot
  change subject, group, memory bank, or authority.
- Production Hermes is not upgraded as part of identity or UI work.

## Known compatibility surface

The HADES-owned Hermes overlay is intentionally narrow and currently covers:

1. local model routing for tool-bearing turns;
2. Hindsight retain/recall normalization and subject-bank selection;
3. shared-state memory-retention suppression;
4. API-side MCP tool reconciliation and household filtering; and
5. weak-model handling for explicit memory and Grocy flows.

Each behavior has an upstream gap, acceptance evidence, and removal condition
in [`hermes-overlay-inventory.md`](hermes-overlay-inventory.md). The overlay
must remain removable without introducing a HADES core/orchestrator.

## Recovery dependencies

The known recovery order is Open WebUI, Hindsight, Grocy, Hermes, Agent Zero,
then SearXNG. Open WebUI, Grocy, identity, and Hindsight export/restore
rehearsals now exist for protected or synthetic state. Complete private
production backup validation remains operator work. Stable subject-to-memory mappings must be restored together;
booting services alone is not recovery evidence.

## Remaining gates

These are deliberate gates, not missing implementation tasks:

- owner-authenticated Hermes 0.21.2 promotion rehearsal;
- owner-approved disposition of the candidate-only Hermes 0.21.2 promotion
  after the documented HADES qualification suite and residual classifications;
- owner-approved Proxmox, NetBox, and Uptime Kuma endpoints and read-only
  credentials;
- owner-approved Home Assistant endpoint, token, and entity allowlist; the
  reusable read-only adapter is staged but not live-enabled;
- product authorization for deterministic automation; and
- operator-managed encryption key custody, off-host destination, retention,
  and plaintext-retirement policy for recovery artifacts.

## Stable-v1 readiness score

This capability score is the roadmap source of truth; it describes readiness,
not commit volume.

| Capability | Status | Smallest remaining contract |
|---|---|---|
| Owner daily-driver | PASS | Fresh owner regression after any runtime promotion; current persistence evidence is retained |
| Household multi-user | PARTIAL | Disposable Qwen long-context harness, real pinned Open WebUI Alpha/Beta private-chat/channel soaks, and the isolated six-image Alpha/Beta model-route/restart-isolation path pass; authenticated Hermes gateway composition and owner-visible acceptance remain |
| Private memory | PASS | Preserve subject mapping through any migration; reload/restart persistence is evidenced |
| Shared household state | PASS | Recipe URL/paste structured-data path, canonical Grocy authoring/fulfillment, and synthetic receipt-intake review path are evidenced; owner-visible recipe and intake acceptance remains |
| Web/search | PARTIAL | Synthetic and credential-free Hermes CLI paths pass the repaired search-only boundary; fresh owner-UI follow-up must confirm search freshness |
| Bounded operator | PASS | Bounded inspection remains available and unsafe delegation is rejected before upstream dispatch; broader tasks and native A2A remain optional hardening |
| Finance | OWNER-GATED | Approve canonical environment, data, credentials, and production scope; owner-scoped local CSV preview/import planning, native CSV/QIF/OFX/QFX/CAMT handoff, and the unregistered reconciled writer contract are dogfood-tested without production writes |
| Homelab | PARTIAL | Synthetic Proxmox/NetBox/Kuma authority reconciliation, bounded Nmap evidence, review-only catalog candidates, and write-free control planning pass; connect approved endpoints with least-privilege credentials and validate real-network freshness |
| Home Assistant | PARTIAL | Synthetic read-only adapter, ordinary-entity reads, stale/unavailable shaping, and security-sensitive filtering pass; connect the approved URL/token/entity allowlist and validate the deployed read path |
| Automation | DEFERRED | Approve one deterministic workflow and rollback contract |
| Recovery | PARTIAL | Synthetic identity/canonical-state restore now passes; complete private encrypted custody, retention, and full-component restore |
| Installation/rebuild | PARTIAL | Two independent fresh Fedora synthetic deployments/reboots, actual-image six-component composition with authenticated Alpha/Beta model routing and restart persistence, and the synthetic household-soak contract pass; complete an independent full application reconstruction and fresh-guest household soak |
| Security | PASS | Static CI guards now cover authority amplification, mounts, pinned deployment, and read-only finance/operator surfaces; re-run after authority-bearing changes |
| Performance | PARTIAL | Prior web/recipe capture is below the repeated ~30s threshold; expanded daily-driver matrix is syntax-checked but needs a reachable model lane for fresh timing evidence |

## Source-of-truth adversarial contract

The synthetic contradiction harness (`scripts/test-source-of-truth-fixture.sh`)
exercises stale Hindsight, runtime, pantry, finance, web, and availability
claims. Current canonical systems win—Proxmox for runtime, Grocy for pantry,
Actual for synthetic finance, and Kuma for observed availability—and a
disagreement is disclosed as a conflict. Memory remains context only; it never
becomes a shadow authority.

No real finance, homelab mutation, Home Assistant security control, or final
installer is part of this readiness record.

Deterministic automation is prepared but not provisioned; its execution
boundary and authorization gate are recorded in
[`automation-boundary.md`](automation-boundary.md).

## Current next action

Continue capability expansion from the highest-value unblocked lane. Receipt
review/intake, Actual native-file handoff, bounded homelab control planning,
synthetic voice dogfood, and Agent Zero unsafe-task screening now have
independent evidence; no production setting changed. The next useful work is
to compose these staged capabilities into owner-like flows and repair any
systemic routing or authority defects. Hermes 0.21.2 promotion and
owner-visible WebUI/recipe/voice acceptance remain explicit gates, not reasons
to alter the production 0.14.0/0.11.1 baseline.
