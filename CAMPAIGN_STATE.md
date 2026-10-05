# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 09:40 UTC

**Mission:** converge useful homelab behavior on current green `main`, close read-only reliability contracts, and reduce architectural concentration. The old GPU-parity branch remains historical reference; do not promote it wholesale.

**Repository:** canonical `origin/main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; exact Public CI `37254848424` passed. The active candidate branch `codex/aster-homelab-clean-candidate-20261005` has code-bearing checkpoint `84ce74c452260d0bc69fe9b0f763ddfbc9c2e13b`, 78 commits ahead of main; exact Public CI `37291258235` passed. That run includes the composer test, current-tree safety, and introduced-history safety. NYX-058 is integrated. A previous pushed checkpoint branch retains a superseded documentation commit that fails introduced-history safety; the active candidate excludes it and no history was rewritten. No candidate is promoted or deployed.

**Reliability and review:** The active candidate is a clean descendant that excludes the superseded path-bearing checkpoint. NYX-036 doctor package/process checks, NYX-037 malformed Proxmox response isolation, NYX-041 activity view extraction, NYX-043/045 backup-reporting corrections, and NYX-046/047/051 summary projection work are included. NYX-053 found no concrete stale-cache-to-live defect; NYX-054 added a sequential Kuma success→heartbeat/config failure regression, reviewed and integrated as `cbdbb399`. The full adapter suite, shell syntax, current-tree safety, and introduced-history checks pass; candidate Public CI passes. NYX-055 found no source-failure household leak; NYX-056 independently verified the sanitized candidate lineage. Current private-infra independent recovery remains a P1: existing local bundles do not contain current private checkout state, and owner-approved off-host destination/recipient are not yet documented.

**Runtime truth:** read-only inspection found the Hermes unit active and its working directory matched the running process cwd, but the process lacked `HADES_HERMES_WORKING_DIRECTORY`. Doctor fails closed; the supported generated unit/profile contract sets the variable, but production requires canonical regeneration before doctor acceptance. Deployed adapter provenance differs from source, and fresh Kuma observations lacked `observed_at`. No production modification occurred.

**Next exact actions:** implement and qualify a provenance manifest for deployment-local Hermes overlay composition across installer, doctor, and deployed-provenance tooling. NYX-060 identified that the current installer overwrites composed overlays and doctor rejects their bytes; NYX-061 is building the isolated manifest validator/test seam. Continue source/runtime parity and representative owner/household acceptance. NYX-059 confirmed private checkout and complete source+records+runtime recovery remain incomplete; keep the dirty private checkout untouched until owner-selected independent custody is available.

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
