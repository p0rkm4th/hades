# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Canonical public `main` is `e93f497e14da7b680612f7d30441a089ad4e22ce`. The named-host workload formatter extraction passed candidate Public CI [37355109128](https://github.com/p0rkm4th/hades/actions/runs/37355109128) and post-promotion main CI [37355337581](https://github.com/p0rkm4th/hades/actions/runs/37355337581). Prior response-boundary test candidate/main CI [37354412609](https://github.com/p0rkm4th/hades/actions/runs/37354412609) / [37354552987](https://github.com/p0rkm4th/hades/actions/runs/37354552987) and documentation checkpoint candidate/main CI [37354002390](https://github.com/p0rkm4th/hades/actions/runs/37354002390) / [37354189687](https://github.com/p0rkm4th/hades/actions/runs/37354189687) passed. The active Aster branch matches main; no unqualified code candidate is ahead.

Mission: reconcile the old homelab line, close achievable read-only reliability gaps, keep one green main, and continue bounded architecture extraction. The current-main guest-visibility renderer extraction and household/missing-subject pre-read denial are merged and green. Deployed Hermes-overlay and homelab-adapter hashes are **NOT VERIFIED** in this epoch, and current-main runtime parity is not established. NYX-001, NYX-002, NYX-004, NYX-007, and NYX-008 are ACCEPTED. NYX-007 added synthetic workload-response boundary coverage; NYX-008 extracted its pure renderer while retaining all authority and source decisions in Hermes.

The homelab read layer remains **PARTIAL** as an owner-facing live capability. No current-main package/runtime byte parity or fresh authenticated owner/household acceptance was established, and no production deployment or canonical-source ACL mutation was performed. Seven authenticated chats on adapter revision `6bc6063702f73665a9cf666ca14cf7057d5924e` remain narrow historical evidence, not acceptance of current main.

The old `codex/gpu-telemetry-parity-20261004` ref was `345cb1b6de5f9f51ad98986c88ab9f0693461921`, based on `b903ad331dc0269becf46600bf29db8931707fef`; latest hosted CI run [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701) failed the public-history check. The introduced-history safety audit reports one local-path/private-address finding (details intentionally withheld). NYX-001 and Aster independently found no unique public-safe behavior to port: main's GPU, inference, identity, freshness, and service-completeness contracts are stronger, while the old tree removes extracted view modules and focused tests. Disposition: **UNSAFE / OBSOLETE REFERENCE; DO NOT MERGE OR IMPORT**. The remote branch ref was deleted after classification; history was not rewritten, and the clean local source worktree remains preserved for reference. Main architecture includes Proxmox host-load/guest views, bounded Kuma/backup/activity/inference views, and provider/config/reconciliation modules. Aster extracted the guest-visibility pure renderer in `4abf11ca`; Hermes retains authorization and source reads. The later `d8013f94` fix denies household and unverified-owner named-host workload reads before fetching the homelab summary.

A follow-up backup-history review found malformed node-discovery rows could make incomplete Proxmox backup coverage appear healthy. The fix at `50919421` tracks these rows, keeps valid-node evidence, marks task coverage PARTIAL, and surfaces an operator warning. NYX-012/013 cleared it; candidate CI passed. Main post-promotion CI run `37346207557` passed.

NYX-015 found that household named-host CPU/memory questions could reach model dispatch with prior conversation history. Main `786afe8` closes named-host and pronoun-only resource follow-ups before model/tool handling, deriving context only from the latest user turn; conceptual computer-memory, Minecraft-memory, and load-balancing questions remain ordinary conversation. NYX-016–018 reviewed the scoped guard, false-positive narrowing, and follow-up context. Runtime regressions require zero model calls, no homelab dispatch, and no host/metric sentinel leakage.

Measured current-main source sizes: `hermes/sitecustomize.py` 12,615 lines / 150 top-level `_hades_*` definitions (174 including nested definitions); `integrations/homelab-readonly/server.py` 1,937 lines / 36 top-level functions; `reconcile.py` 375 lines; `config.py` 156 lines; `kuma.py` 62 lines; `backup_view.py` 142 lines; `activity_view.py` 90 lines; `inference_view.py` 946 lines; `homelab_views.py` 536 lines. The guest-visibility renderer moved without behavior change; focused parity cases cover all status/scope branches and source read time. Household and missing-subject named-host workload requests now return before any summary/source read, with zero-read regression assertions. These are measurements, not targets by themselves.

Private infrastructure recovery remains owner-managed and unresolved: the owner confirmed no off-site backup currently exists and could not name an independent encrypted target or recipient. No recovery artifact was made; same-disk copies are not independent disaster recovery. Keep topology, credentials, and raw acceptance material in protected records.

**Next exact action:** continue owner-client DNS/runtime acceptance using a verified canonical name and exact deployed package provenance; coordinate any host/network repair with Nyx-4. If owner UI remains unreachable, pursue bounded source freshness/partial-outage checks without implying production parity. Keep homelab and private-infra recovery PARTIAL; no independent recovery destination or recipient has been selected, so do not create or claim off-site restore custody.

## Previous code and dogfood checkpoints — 2026-10-04

The homelab code checkpoint `f55bd0a` completed the bounded broad status
slice after owner/household dogfood and correction of a display-label conflict
misclassification. Earlier code checkpoint `86ca48f` completes the inference
freshness and aggregated-GPU display slice. Code checkpoint `8b28cae` separates
hardware-observation freshness; checkpoint `07b0055` added NetBox pagination
completeness and contradictory-coverage handling. Public CI run `37236639218`
passed for the earlier source checkpoint. The adapter
requires valid `count`, `next`, and `results` metadata before calling a
service catalog complete or empty; missing pages and malformed/contradictory
metadata remain partial or unknown. Focused synthetic contracts pass.

Fresh owner dogfood found that the tracked hardware matrix's successful file
read (`status=OK`) was incorrectly being reused as its data freshness. The
adapter now classifies `observed_at` independently using the documented
seven-day window (`FRESH`, `STALE`, or `UNKNOWN`), while retaining `status=OK`
solely for read success. Hermes consumes only the explicit freshness field.
Focused synthetic tests cover the age boundary, invalid/future timestamps, and
the status/freshness separation. Public CI run `37238630968` passed at
`86ca48f`. A fresh owner UI answer uses the seven-day classification without
calling a successful read `ok`, preserves the aggregate `4x Quadro P4000`
label, and distinguishes timestamped GPU telemetry from recorded hardware
inventory. The answer also retains provider-residency, generation, and host
health limitations. Household game-server status remains unknown without
leaking owner topology. Hermes and WebUI health passed after rollout. The
freshness, answer-formatting, and aggregate-count defects are closed; the
broader live homelab reliability campaign remains partial.

Fresh owner dogfood then found that “Is everything okay with the homelab?”
fell through to a long inventory answer. The owner route now returns a bounded
health summary: fresh configured availability checks, Proxmox guest power
state with its application-health limitation, incomplete service placement,
unmonitored services, and backup-content/restoreability limits. A fresh owner
follow-up distinguishes shared display labels from cross-source conflicts.
The first deployed formatter candidate called duplicate labels a source
disagreement; owner dogfood caught this, hash-guarded rollback restored the
previous overlay, and the corrected candidate was deployed after the conflict
classification was fixed. Fresh owner/household UI checks pass; Household A
still receives no internal topology and HADES correctly cannot confirm game
server health without an approved current check. Public CI run `37240583967`
passed at `f55bd0a`. This closes the broad-summary wording slice, not the
broader live homelab reliability campaign.

A first private composition attempt removed adjacent helpers and caused an
owner-chat error. Hash-guarded rollback restored both prior files and health.
The corrected function-scoped overlay composition passed its protected
synthetic review and was deployed with the matching adapter module. Fresh
owner UI checks now distinguish the explicitly empty NetBox catalog from
unknown coverage, refuse remembered Minecraft placement, and retain the
bounded Agent Zero endpoint answer. Household A received no internal host or
address details. Hermes and Open WebUI health checks passed after restart.

The change updates only HADES read-only runtime code. No Proxmox, NetBox, Kuma,
host, driver, guest, network, account, source ACL, or source-access
configuration changed. Private hashes, rollback paths, and raw owner/household
transcripts remain in protected operator records.

The current source tree removes private destination acceptance records and
per-user share mappings, requires explicit destination hostname input, and uses
synthetic guest names in fixtures. Current-tree safety, introduced-history
path/address audit, and the known-private-literal scan pass. Existing public
history is not rewritten; older reachable commits retain previously published
private identifiers. Do not claim historical erasure or merge from an older
candidate ref.

The deployment changed only the composed Hermes overlay and profile-selected
read-only HADES adapter. No Proxmox, NetBox, Kuma, host, driver, guest, network,
account, source ACL, or source-access configuration changed.

## Homelab read reliability

The read-only adapter composes Proxmox runtime, NetBox intended inventory,
Uptime Kuma observations, inference providers, and explicitly configured
telemetry. Owner output distinguishes source timing, stale observations,
source disagreement, and unknown runtime state. Household summaries remain
redacted. Synthetic adapter coverage seeds a stable Proxmox-to-NetBox identity
link, then makes NetBox unavailable; live runtime remains while the prior
inventory identity disappears, and stale Kuma data stays stale. Owner broad
status now avoids a raw inventory dump and distinguishes fresh probes from
guest power state, service-coverage gaps, and backup limits.

Fresh owner dogfood for “Why does the network feel slow?” returned only
configured-probe timings and runtime samples, then explicitly declined a
network-wide diagnosis. Packet loss, throughput, DNS timing, and historical
comparison remain unavailable; the household “Why is everything slow?”
answer exposed no private topology. Network performance remains unverified.

Authenticated synthetic UI acceptance exposed a registration gap: deterministic
owner routes could run before the local read-only adapter fallback was
registered. After MCP discovery returned no handler, the route incorrectly
reported the source as unconfigured. The route now registers the same bounded
owner-only fallback used by tool discovery. The authenticated acceptance passed
with synthetic identities and sources.

## Remaining homelab read-reliability work

- Continue live stale/partial-source acceptance, native service-health and
  service-placement coverage, network measurements, and bounded inference
  capacity checks. A separate owner backup query returns bounded configured
  job/task records with explicit attribution and restoreability limits, but
  coverage and recovery remain open. The current game-server health source
  remains unconfigured.
- Complete backup-custody, reboot, and end-to-end restore evidence before
  claiming recovery readiness.
- Keep infrastructure reads read-only; write authority is outside this
  campaign.
