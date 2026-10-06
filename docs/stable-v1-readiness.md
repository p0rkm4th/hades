# HADES stable-v1 readiness

This is a readiness record for the deployment, not an installer or a new
runtime layer. Most component observations below were last rechecked read-only
on 2026-09-25 and remain dated evidence. The Homelab row records repository
reliability and household-boundary work through 2026-10-05. A fresh bounded
owner/household acceptance run passed on the currently reachable deployment,
but it does not establish current-main runtime parity.

## Engineering release convergence (2026-10-01)

The qualified release SHA `e7f4fa83e1970257ea522109828b4193827df28e` passed hosted Public CI runs [36896358861](https://github.com/p0rkm4th/hades/actions/runs/36896358861) and [36896801928](https://github.com/p0rkm4th/hades/actions/runs/36896801928), before and after fast-forward promotion. Both runs completed 110/110 reported steps with zero failures or skips. The implementation includes subject- and conversation-bound confirmation, exact provisioning-plan checks, and authenticated synthetic cross-worker acceptance. This is repository and synthetic verification only; production was not changed.

Before promotion, the public base had one tip-tree private-path/address match
and 90 matches in reachable history. The fast-forwarded release tree passes
the current-tree guard; the 90 legacy history matches remain. Current-tree and
introduced-release Gitleaks scans have no findings. No old public history was
rewritten.

## Observed component contract (last read-only recheck: 2026-09-25)

| Component | Production role | Current state | Canonical authority |
|---|---|---|---|
| Open WebUI | owner-facing conversation surface | pinned 0.11.1 deployment | conversations, users, settings |
| Hermes | agent execution and tool lifecycle | 0.21.2 active on HADES guest; systemd running, zero restarts at 2026-09-25 01:43 UTC; 0.14.0 rollback artifact retained | turn execution and tool results |
| Hindsight | durable personal context | healthy, subject-scoped overlay | private semantic memory |
| Grocy | household pantry and grocery state | healthy, shared | inventory, shopping, recipes |
| SearXNG | web search | healthy, private | search results and freshness |
| Agent Zero | bounded subordinate operator | healthy, owner-scoped | delegated task evidence |
| LLDAP | staged/production identity foundation | private and persistent | directory identity and groups |
| Homelab substrate | owner-only infrastructure reads | Proxmox, NetBox, and Kuma inputs were previously configured and authorized; a narrow authenticated run passes on the currently reachable deployment, but current-main runtime/package parity and acceptance against that exact package remain unverified | Proxmox runtime; NetBox intended inventory; Kuma observed availability |

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

These include remaining implementation work and owner/operator gates:

- owner-authenticated acceptance of the migrated HADES instance on hypervisor host HADES guest, authoritative `hades.example.invalid` DNS/DHCP cutover, client verification, and
  only then the allowlisted laptop production shutdown/cleanup;
- track the isolated upstream SQLite repair-test failure for Hermes 0.21.2;
  current live gateway/model health is accepted and the issue alone does not
  trigger rollback;
- close the remaining deep inference provider/specialized inference provider GPU-container and separately repeated
  persistence gates, locate the planned seventh server, resolve the 100 Mb/s
  hypervisor host link, and complete live freshness/conflict/failure acceptance;
  `.113` is already classified as an excluded Sony PS5;
- owner-approved Home Assistant endpoint, token, and entity allowlist; the
  reusable read-only adapter is staged but not live-enabled;
- operation-time authority, idempotent recovery, and result-isolation proof for
  the four already-authorized read-only automation templates; and
- operator-managed encryption key custody, off-host destination, retention,
  and plaintext-retirement policy for recovery artifacts.

## Stable-v1 readiness score

This capability score is the roadmap source of truth; it describes readiness,
not commit volume.

| Capability | Status | Smallest remaining contract |
|---|---|---|
| Owner daily-driver | OWNER-GATED | Complete owner-visible acceptance on the migrated HADES guest instance, authoritative `hades.example.invalid` cutover, and client verification before disabling laptop production |
| Household multi-user | PARTIAL | Disposable Qwen long-context harness, real pinned Open WebUI Alpha/Beta private-chat/channel soaks, fresh Rocky generated-installer Hermes/WebUI Alpha/Beta model-route/restart-isolation, and synthetic memory/Grocy/web composition pass; owner-visible authenticated composition and model-quality acceptance remain |
| Private memory | PASS | Preserve subject mapping through any migration; reload/restart persistence is evidenced |
| Shared household state | PASS | Recipe URL/paste structured-data path, canonical Grocy authoring/fulfillment, and synthetic receipt-intake review path are evidenced; owner-visible recipe and intake acceptance remains |
| Web/search | OWNER-GATED | Synthetic and credential-free Hermes CLI paths pass the repaired search-only boundary, including fresh follow-up semantics and search-vs-page provenance; fresh authenticated owner-UI follow-up must confirm search freshness |
| Bounded operator | PASS | Bounded inspection remains available and unsafe delegation is rejected before upstream dispatch; broader tasks and native A2A remain optional hardening |
| Finance | OWNER-GATED | Approve canonical environment, data, credentials, and production scope; owner-scoped local CSV preview/import planning, native CSV/QIF/OFX/QFX/CAMT handoff, and the unregistered reconciled writer contract are dogfood-tested without production writes |
| Homelab | PARTIAL | Public main at checkpoint `8e47674112d6797ccb56a5892a02ec3b5475e2b7` passed CI [37392606825](https://github.com/p0rkm4th/hades/actions/runs/37392606825). Clean current-main candidate code commit `868524d6` has the same source tree as `54afe585`, which passed candidate CI [37394170918](https://github.com/p0rkm4th/hades/actions/runs/37394170918); it extracts pure service-monitor response handling into the already-packaged views module while Hermes retains owner authorization and target classification. NYX-001 found no safe required old-branch behavior missing from main; unsafe historical changes remain unimported. Focused synthetic source, freshness, conflict, identity, backup, inference/GPU, and household-redaction contracts pass. Full deployed adapter/profile/overlay lineage and loaded bytes remain unverified; NYX-124 found no verified active-overlay base or reusable protected runtime host-key profile. No production deployment or fresh current-source owner/household acceptance is claimed. Owner has no off-site backup target/recipient; no recovery artifact or restore proof exists. Keep PARTIAL until trusted source/runtime provenance and fresh authenticated owner/household acceptance are established. |
| Home Assistant | PARTIAL | Synthetic read-only adapter, ordinary-entity reads, stale/unavailable shaping, and security-sensitive filtering pass; connect the approved URL/token/entity allowlist and validate the deployed read path |
| Automation | PARTIAL | The joined disposable Phase 3 path passes on two independent pristine Fedora 44 x86_64 guests with SELinux enforcing: immutable n8n and LLDAP pins, generated Epsilon package under strict transient systemd, Hermes 0.21.2 result route, authenticated Open WebUI Alpha/Beta/Gamma, shared/unshared isolation, live Beta grant revocation, and duplicate signed run replay after service restart. The second guest passed again after a real reboot with Docker automatically active. Synthetic contracts cover expired-lease UNKNOWN suppression, failure redaction, ten concurrent maximum-quota requests with replay, and post-poll schedule rollback. The resolver does not query Open WebUI-only account disable. Production Phase 3 keys, state, group mapping, endpoint, and scoped n8n credential remain unprovisioned; schedules stay inactive |
| Recovery | PARTIAL | Synthetic identity/canonical-state restore now passes; complete private encrypted custody, retention, and full-component restore |
| Installation/rebuild | PARTIAL | Two independent fresh Fedora synthetic deployments/reboots, the fresh Rocky generated-installer seven-component path with authenticated Hermes/WebUI Alpha/Beta restart/isolation and post-reboot Hermes/container recovery, and the synthetic household-soak contract pass; prove owner-visible composition on a reconstructed deployment |
| Security | PARTIAL | The promoted release tree passes current-tree safety, its introduced-history range passes `scripts/public-history-audit.sh`, and Gitleaks reports no findings in the current tree or introduced release commits. Before promotion, the public base had one tip-tree private path/address match and 90 matches in reachable history. The tip-tree finding was removed; 90 legacy matches remain in published history. No history rewrite was performed. |
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

The four named read-only automation templates have standing owner
authorization. The runner now has a signed repository endpoint backed by live
LLDAP membership, but neither is deployed or connected to n8n. Keep schedules
disabled; see
[`automation-boundary.md`](automation-boundary.md).

## Current next action

Commit and qualify the documentation-inclusive current-main candidate, then
fast-forward only that green descendant and verify main CI. Keep the homelab
capability PARTIAL: the service-health view extraction is source-tested, but
full active adapter/profile/overlay lineage, loaded Python identity, and fresh
authenticated current-source owner/household acceptance remain unverified.
Production stays unchanged until a verified strict host-key profile and exact
active-overlay base permit safe read-only acceptance. No off-site recovery
destination is available or identified; do not create an unapproved artifact.
