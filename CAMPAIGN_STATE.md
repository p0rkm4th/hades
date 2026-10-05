# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 10:51 UTC

**Mission:** converge useful homelab behavior on current green `main`, close read-only reliability contracts, and reduce architectural concentration. The old GPU-parity branch remains historical reference; do not promote it wholesale.

**Repository:** canonical `origin/main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; exact Public CI `37254848424` passed. The active current-main descendant `codex/aster-homelab-clean-candidate-20261005` has latest code checkpoint `4ab862a37aa28ad4b73a76720d65b96a57591251`; exact Public CI `37299052704` passed. Current-tree safety and the introduced-history audit from `origin/main` both pass on this code. No candidate promotion or rollout has occurred.

**Reliability and review:** NYX-058/061 function-scoped overlay composition and source/tree manifest verification are integrated. The installer preserves a customized overlay only with a verified manifest and safely preserves it on reruns; doctor, validator, and deployed provenance check the same source/artifact/install-marker identity and reject unsafe modes. NYX-062/063 trust gaps were repaired; NYX-064 found no remaining P1/P2 in that contract. NYX-066 extracted pure Proxmox host-load rendering into the existing view module. NYX-068, 071, and 073 successively reproduced household host-detail prompts crossing to model dispatch without reading homelab data. NYX-069/072/074 add denial coverage for plain, quoted, backticked, curly-quoted, and parenthesized host names plus host-memory-use phrasing. Aster reviewed and integrated NYX-074 as `4ab862a`; runtime/service-health focused tests, Public CI `37299052704`, current-tree safety, and introduced-history safety pass. A fresh production inspection separately confirms substantial adapter/module and process-environment drift, so source-to-runtime parity is still a P1 gap. Private-infra independent recovery is also owner-gated: current private checkout recovery and external custody remain unproven.

**Runtime truth:** a strict-host-key read-only probe at 2026-10-05 10:35 UTC confirmed the Hermes systemd service active, its configured working directory, and an executable path for Hermes 0.21.2. The deployment Git metadata reports `b102dfd`, but full worktree status could not be established. A live MCP child executes an older generated adapter tree: two modules differ from the candidate and five current source modules are absent. The running process also lacks `HADES_HERMES_WORKING_DIRECTORY`, `PYTHONPATH`, and explicit adapter-path variables. Root-only hashes confirmed the active overlay is customized; protected profile values were not read. Runtime package parity, freshness semantics, process-environment compliance, and application health remain unverified. The overlay-preserving composition path is synthetically verified but not applied. No infrastructure source access, ACL, host, network, or driver changes were made.

**Next exact actions:** obtain NYX-075's independent review of the deployment composition/parity plan; then use the supported overlay-preserving procedure to reconcile the active adapter package and customized overlay against the exact candidate, with protected backups and hash-guarded rollback, before owner/household dogfood. Verify the process environment and functional answers after rollout. Keep stale, partial, and contradictory source semantics explicit. Private checkout recovery/custody remains owner-gated; leave the dirty private repository untouched until an owner-selected independent destination and encryption recipient exist.

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
