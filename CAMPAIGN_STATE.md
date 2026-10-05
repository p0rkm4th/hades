# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 07:53 UTC

**Mission:** converge safe, useful homelab behavior onto current green `main`, close read-only reliability contracts, then make bounded architecture extractions. The old GPU-parity branch remains unsafe historical reference and is not eligible for wholesale promotion.

**Repository:** canonical `origin/main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; exact Public CI [37254848424](https://github.com/p0rkm4th/hades/actions/runs/37254848424) passed. Aster integration branch `codex/aster-homelab-checkpoint-redacted-20261004` is based on that main. NYX-034 candidate `1684f78736d015dd6ea25fa869e4a90694993cf9` passed exact CI [37277326937](https://github.com/p0rkm4th/hades/actions/runs/37277326937); NYX-035 installer closure `b8258e8724219cd34cb31c37b9d9165736b5440e` passed within status checkpoint CI [37278311508](https://github.com/p0rkm4th/hades/actions/runs/37278311508). Candidate `c5e865aca1f78a70598d50bae4a11b919039351c` extracts Proxmox guest-visibility rendering into the existing view module and passed exact Public CI [37278760219](https://github.com/p0rkm4th/hades/actions/runs/37278760219). NYX-036 doctor-time package drift checks are now integrated through `57d4c14e`; focused package-drift, manifest, reconstruction, doctor-exit, deployment-provenance, and closure tests pass locally. The combined candidate through `3dac7d2f` passed exact Public CI `37280194670`. `sitecustomize.py` is 12,731 lines / 150 `_hades*` definitions; `homelab-readonly/server.py` is 1,940 lines. Nothing is promoted to `main` or deployed.

**Runtime truth:** deployed provenance remains distinct from source. Prior read-only inspection found mixed generated adapter modules and fresh availability rows without Kuma `observed_at`; this remains a live contract failure. Service placement remains unknown where NetBox coverage is empty. Household intent denial and package changes require fresh deployed owner/household verification before any production claim.

**Reviews and gates:** NYX-032 provenance bypass fix and NYX-034 authenticated-redirect guard are source-integrated; exact CI `37277326937` passed for the latter's source/docs checkpoint. NYX-035 is integrated and included in exact Public CI `37278311508` (pass). NYX-036 is source-integrated locally; exact Public CI `37280194670` passed for `3dac7d2f`. Nyx's c5 extraction review found no material issue; a final adversarial pass on the active-unit environment check is underway. No production deployment, main promotion, or live source-access change occurred in this checkpoint. P0/P1 and owner dogfood gates remain as recorded below and in the protected coordination file.

**Next exact actions:** qualify the combined candidate and close the active-unit falsification review. Then continue required read-reliability and architecture work before candidate qualification. Keep deployment separate, with existing owner authorization, rollback, and fresh owner/household checks.

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
