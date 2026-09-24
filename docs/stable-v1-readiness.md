# HADES stable-v1 readiness

This is a readiness record for the current product contract, not an installer
or a new runtime layer. The current source/deployment pin is Hermes 0.21.2;
private owner acceptance and component-specific gates remain separate from
source-level readiness.

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
| Homelab substrate | owner-only infrastructure reads | Proxmox, NetBox, and Kuma published read paths live | Proxmox runtime; NetBox intended inventory; Kuma observed availability |

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

- owner-authenticated acceptance of the migrated HADES instance on Erebus VM
  802, authoritative `hades.local` DNS/DHCP cutover, client verification, and
  only then the allowlisted laptop production shutdown/cleanup;
- owner-authenticated Hermes 0.21.2 promotion rehearsal;
- owner-approved disposition of the candidate-only Hermes 0.21.2 promotion
  after the documented HADES qualification suite and residual classifications;
- close the remaining Tartarus/Hypnos GPU-container and separately repeated
  persistence gates, locate the planned seventh server, resolve the 100 Mb/s
  Erebus link, and complete live freshness/conflict/failure acceptance;
  `.113` is already classified as an excluded Sony PS5;
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
| Owner daily-driver | OWNER-GATED | Complete owner-visible acceptance on the migrated VM 802 instance, authoritative `hades.local` cutover, and client verification before disabling laptop production |
| Household multi-user | PARTIAL | Disposable Qwen long-context harness, real pinned Open WebUI Alpha/Beta private-chat/channel soaks, fresh Rocky generated-installer Hermes/WebUI Alpha/Beta model-route/restart-isolation, and synthetic memory/Grocy/web composition pass; owner-visible authenticated composition and model-quality acceptance remain |
| Private memory | PASS | Preserve subject mapping through any migration; reload/restart persistence is evidenced |
| Shared household state | PASS | Recipe URL/paste structured-data path, canonical Grocy authoring/fulfillment, and synthetic receipt-intake review path are evidenced; owner-visible recipe and intake acceptance remains |
| Web/search | OWNER-GATED | Synthetic and credential-free Hermes CLI paths pass the repaired search-only boundary, including fresh follow-up semantics and search-vs-page provenance; fresh authenticated owner-UI follow-up must confirm search freshness |
| Bounded operator | PASS | Bounded inspection remains available and unsafe delegation is rejected before upstream dispatch; broader tasks and native A2A remain optional hardening |
| Finance | OWNER-GATED | Approve canonical environment, data, credentials, and production scope; owner-scoped local CSV preview/import planning, native CSV/QIF/OFX/QFX/CAMT handoff, and the unregistered reconciled writer contract are dogfood-tested without production writes |
| Homelab | PARTIAL | Seven-host acceptance is in progress: Proxmox, NetBox, and the Kuma published read path are live; authenticated owner dogfood answers live Proxmox status, separates GPU inventory from liveness, and exercises bounded review-only LAN discovery; VM 802 is live as the HADES destination, its clean Hermes `b102dfd` source/runtime candidate is active, the complete protected rollback package is independently verified, and private Hermes model execution passes; the read-only preflight and final verifier now validate whole-package checksums, separate encryption custody from rollback readiness, and require explicit laptop cleanup evidence; its NetBox intended-inventory record and two Kuma destination monitors remain plan-only until the address reservation is authoritative; the conservative workload-oriented [compute capability map](homelab-compute-capability-map.md) records Tartarus as 4× P4000 and Hypnos as 2× P4000 with native CUDA-driver smoke, SMART evidence, Podman/NVIDIA CDI runtime configuration, and controlled reboot persistence; both Rocky hosts are reachable and their existing `eno1` profiles autoconnect on boot, while GPU-container execution remains open; Hermes' controlled reboot requires console/power recovery after ARP/SSH failure; Thanatos remains a live temporary management plane, is firmware-gated for NVIDIA activation, provides a temporary QNetd candidate reachable only from the two Proxmox nodes, and has a historical SMART anomaly on `/dev/sdd` requiring hardware follow-up; `.113` is confirmed as an excluded Sony PS5, so the planned seventh server must still be located; Erebus has a 100 Mb/s link; close the remaining runtime/recovery gates and validate freshness/conflicts/failure handling |
| Home Assistant | PARTIAL | Synthetic read-only adapter, ordinary-entity reads, stale/unavailable shaping, and security-sensitive filtering pass; connect the approved URL/token/entity allowlist and validate the deployed read path |
| Automation | DEFERRED | Approve one deterministic workflow and rollback contract |
| Recovery | PARTIAL | Synthetic identity/canonical-state restore now passes; complete private encrypted custody, retention, and full-component restore |
| Installation/rebuild | PARTIAL | Two independent fresh Fedora synthetic deployments/reboots, the fresh Rocky generated-installer seven-component path with authenticated Hermes/WebUI Alpha/Beta restart/isolation and post-reboot Hermes/container recovery, and the synthetic household-soak contract pass; prove owner-visible composition on a reconstructed deployment |
| Security | PARTIAL | Current-tree safety, authority-amplification, mounts, pinned deployment, and read-only finance/operator guards pass; reachable pre-redaction commits still contain private topology/path values, so retire or rewrite the affected public history under explicit release authorization and rerun `scripts/public-history-audit.sh` |
| Performance | PARTIAL | Prior web/recipe capture is below the repeated ~30s threshold and the expanded synthetic daily-driver matrix now records model/tool/continuation attribution; a real model lane is still required for human-facing timing decisions |

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

Continue capability expansion from the highest-value unblocked lane. The
composed synthetic household dogfood, fresh Rocky reconstruction, performance
attribution, protected recovery-bundle refresh, and clean Hermes 0.21.2 core
qualification now have independent evidence; no production setting changed.
The next useful work is to finish the unblocked infrastructure acceptance and
reconcile any live-path defects it exposes. Hermes 0.21.2 promotion and
owner-visible WebUI/recipe/voice acceptance remain explicit gates, not reasons
to alter the production 0.14.0/0.11.1 baseline.
