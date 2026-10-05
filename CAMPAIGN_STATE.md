# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Public `main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; exact Public CI run [37254848424](https://github.com/p0rkm4th/hades/actions/runs/37254848424) passed. The Aster integration branch `codex/aster-homelab-convergence-20261005` was created from this exact green head and currently has no code delta. The old `codex/gpu-telemetry-parity-20261004` branch remains a source reference at `345cb1b6de5f9f51ad98986c88ab9f0693461921`, merge base `b903ad331dc0269becf46600bf29db8931707fef`; its latest Public CI run [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701) failed the public-history safety check. No old-branch history or code has been imported. NYX-001 compared both branch tips and is **ACCEPTED**: current-tree safety passes on both, but the old introduced history fails its public-history audit. The old branch adds no safe unique capability to current `main`; it regresses NetBox pagination completeness, Kuma observation timestamps, partial-source service-health handling, and inference freshness/count wording. Do not merge or port it.

Current-main concentration is measured at 12,804 lines / 219 AST function nodes in `hermes/sitecustomize.py` (174 `_hades_*`-named nodes), 2,099 lines / 40 in `integrations/homelab-readonly/server.py`, 375 / 6 in `reconcile.py`, 156 / 11 in `config.py`, 946 / 6 in `inference_view.py`, and 266 / 6 in `homelab_views.py`. This records size only; extraction priorities remain subject to behavior and dependency review.

The public docs and prior protected records describe a deployment-local Hermes composition, but source/runtime parity and the active overlay/adapter hashes have not been rechecked in this campaign epoch. No deployment, host, network, driver, source-ACL, or backup mutation occurred. Prior owner/household dogfood and restore observations remain dated evidence, not current acceptance. The homelab read layer remains **PARTIAL**; live failure/conflict behavior, service health/placement, network trends, complete restoreability, and independent private-infra recovery are not proven current.

Private-infra recovery remains an owner-managed gate: the existing checkout is dirty, and independent encrypted off-host custody and restore proof are not established. No local copy will be described as independent recovery.

**Repository state:** public `origin/main` is canonical. The dirty primary checkout and old parallel worktrees are preserved; this integration branch is the only active Aster implementation line. No private topology, credentials, or raw acceptance transcripts belong in public docs.

**Next exact actions:** commit and qualify this reconciled checkpoint on the integration branch, then begin the first low-risk architecture seam: extract the pure backup response formatter from `server.py` while keeping source reads and Proxmox guest-scope decisions in the server. NYX-001 recommends `backup_view.py` first and recent-activity presentation second. Recheck live runtime provenance before any deployment claim.

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
