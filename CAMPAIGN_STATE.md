# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

**Mission:** converge useful homelab behavior onto current green `main`, reject unsafe parallel history, close achievable read-only reliability contracts, then make bounded architecture extractions. No old homelab branch is eligible for wholesale promotion.

**Repository:** freshly fetched public `origin/main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; Public CI run [37254848424](https://github.com/p0rkm4th/hades/actions/runs/37254848424) passed on that exact SHA. Aster's integration branch `codex/aster-homelab-checkpoint-redacted-20261004` is at `a597283e6c0b676fdc214832b53dd6248b0ab8fa`; Public CI run [37262696829](https://github.com/p0rkm4th/hades/actions/runs/37262696829) passed all 117 steps on that exact docs checkpoint. Its source candidate `7de443d7b8bf3416c2a1287167edd5387b5303ab` passed CI run `37261433008`; the five current-state documents now include Aster's refreshed lineage findings. The branch is not promoted or deployed. The primary local checkout remains preserved and is not the integration base.

The old `codex/gpu-telemetry-parity-20261004` line remains review-only at `345cb1b6de5f9f51ad98986c88ab9f0693461921`, merge base `b903ad331dc0269becf46600bf29db8931707fef`. GitHub Public CI run `37222211701` is confirmed failed at `Check public history`. Aster's current comparison found six added server helpers largely duplicate extracted view helpers on main; the changed formatter loses capability freshness and provider-read timestamps/counts. The old line also removes Kuma `observed_at` from reconciliation and drops NetBox pagination-coverage classification (`COMPLETE`/`EMPTY`/`PARTIAL`/`UNKNOWN`), while its final history auditor removes the narrow upstream-container-path false-positive filter. It deletes two extracted view modules, removes focused contract assertions, and increases combined `sitecustomize.py` plus adapter size by about 800 lines. Current main retains the stronger freshness, service-coverage, and extracted-view contracts. No unique safe behavior has been accepted for import. NYX-018 is independently reviewing this classification.

Homelab source main preserves Kuma `last_updated` as `availability_summary[].observed_at`, separate from freshness. The current active package remains mixed: its entry module matches tracked source, while a reconciliation sibling differs. A direct read-only source call reached configured sources with complete guest-audit coverage; the NetBox application-service catalog was empty, so placement remains unknown. The adapter output reported fresh availability but omitted `observed_at`. Authenticated live owner UI dogfood produced timestamped source summaries, current GPU telemetry with model-fit uncertainty, and an explicit unknown for Agent Zero placement. Household A/B UI checks kept ordinary status abstract. A hostile household inventory prompt exposed an intent-guard gap: the answer promised to query owner sources and named generic source types but returned no concrete host data. Candidate `7de443d7` adds an early deterministic denial for private inventory/administrative-detail requests; focused tests and Public CI pass, but it is not deployed and requires fresh post-deployment household verification. No host/service/source configuration change was made.

Aster's current-main versus old-line source review found an additional old-tree privacy guard regression: the old service-health helper drops its owner-scope check and the route no longer passes scope; its focused test exercises the household denial separately but not the household service-health route. This does not establish a live disclosure. The old NetBox path also collapses missing coverage metadata into an empty-catalog answer and omits current-main unavailable-source/identity assertions. The candidate's focused adapter, inference, service-health, and restore-guest contracts pass locally; NYX-018 is independently rechecking the semantic classification. No old-line code is being imported.

The pure backup formatter extraction is at `10dd2fd1`; its focused adapter contract and Public CI pass, while main promotion remains open. Commit `d0c74306` adds a provenance check that compares the profile-selected generated homelab adapter's complete Python module set and bytes against the clean tracked package; fixtures reject changed content, extra modules, and symlinked package paths. Commit `7de443d7` adds the household private-detail denial with focused regression cases. Focused tests, public-safety checks, introduced-history audit, and Public CI run `37261433008` pass. The five current-state documents were reconciled in `a597283e` and passed Public CI run `37262696829`; current review of the old lineage remains pending. Neither source change is deployed. Earlier package/privacy reviews and the separately owned NYX-015 Thanatos driver follow-up remain recorded in the protected coordination note.

Prior bounded dogfood found complete-empty service inventory and responding probes without claiming application readiness; owner change-history output discloses its limited coverage, and Household A's topology request was denied. These dated results do not close live outage/contradiction, native service-health/placement, normal-user failure acceptance, network trends, or restoreability. The homelab campaign remains **PARTIAL**. Backup tasks and an application archive were inspected, but full application restore and independent-device/off-host custody remain unproven. Exact runtime hashes, private topology, rollback paths, and raw acceptance transcripts stay in protected operator records.

**Next exact actions:** complete NYX-018 independent old-line classification; disposition the source/package/privacy reviews that remain relevant; then promote only the reviewed current-main descendant. After a hash-guarded rollback review, deploy only the household boundary fix to the preserved active overlay, verify Household A/B denial and safe Minecraft status, then reconcile the generated adapter coherently and verify live `observed_at` parity. Keep owner UI placement and full restore claims bounded by the evidence.

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
