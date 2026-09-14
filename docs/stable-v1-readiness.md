# HADES stable-v1 readiness

This is a readiness record for the current deployment, not an installer or a
new runtime layer. Production remains on the known-good Hermes 0.14.0 path
while the Hermes 0.21.2 promotion branch is parked on owner authentication.

## Current component contract

| Component | Production role | Current state | Canonical authority |
|---|---|---|---|
| Open WebUI | owner-facing conversation surface | pinned 0.11.5 deployment | conversations, users, settings |
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
- a clean Hermes 0.21.2 full-suite run, or an explicitly documented hermetic
  disposition for the five host/update-shim/browser-environment residual tests
  and the upstream FTS5 trace-observation assertion;
- owner-approved Proxmox, NetBox, and Uptime Kuma endpoints and read-only
  credentials;
- owner-approved Home Assistant endpoint, token, and entity allowlist;
- product authorization for deterministic automation; and
- operator-managed encryption key custody, off-host destination, retention,
  and plaintext-retirement policy for recovery artifacts.

## Stable-v1 readiness score

This capability score is the roadmap source of truth; it describes readiness,
not commit volume.

| Capability | Status | Smallest remaining contract |
|---|---|---|
| Owner daily-driver | PASS + PERSISTENCE | Fresh owner regression after any runtime promotion |
| Household multi-user | PASS + PERSISTENCE | Longer owner conversation dogfood remains useful hardening |
| Private memory | PASS + PERSISTENCE | Preserve subject mapping through any migration |
| Shared household state | PASS + PERSISTENCE | Complete recipe-authoring browser sequence |
| Web/search | PARTIAL | Fresh owner-UI follow-up must confirm repaired search freshness |
| Bounded operator | PASS + PERSISTENCE | Broader tasks and native A2A remain optional hardening |
| Finance | OWNER-GATED | Approve canonical environment, data, credentials, and production scope |
| Homelab | OWNER-GATED | Approve endpoints, inventory scope, and read-only credentials |
| Home Assistant | OWNER-GATED | Approve URL, token, entity allowlist, and exposure path |
| Automation | DEFERRED | Approve one deterministic workflow and rollback contract |
| Recovery | PARTIAL | Complete private off-host custody, retention, and restore drill |
| Installation/rebuild | PARTIAL | Reconcile the documented reconstruction manifest before packaging |
| Security | PASS | Re-run the boundary matrix after any authority-bearing change |
| Performance | PARTIAL | Capture one fresh owner-approved web and recipe turn with model/tool/continuation stages; optimize only repeated >30s workflows |

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

Continue synthetic/runtime dogfood only when it can reveal a new systemic
defect. If no new defect appears, preserve this stable production checkpoint
and resume the first gated milestone when its required authority becomes
available.
