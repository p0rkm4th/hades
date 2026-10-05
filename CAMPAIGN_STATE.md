# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 12:28 UTC

**Mission:** converge useful homelab behavior on current green `main`, close read-only reliability contracts, and reduce architectural concentration. The old GPU-parity branch remains historical reference; do not promote it wholesale.

**Repository:** canonical `origin/main` remains `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`, exact Public CI `37254848424` passed. Current-main code candidate `55ee5b00740003be795b20c33d06b5b602e8d524` passed exact Public CI `37309643121`; public tree/history safety passed. The canonical-installer rollout runbook isolates staged SearXNG writes and defines preconditions for secrets, ACL/modes, accounts, Grocy MCP, networks, Compose, systemd, and symlinked paths, plus a hash-guarded rollback set. NYX-089 found no remaining P1/P2 gap in that write-set and rollback coverage. No production rollout has occurred.

**Reliability and review:** NYX-058/061 function-scoped overlay composition and source/tree manifest verification are integrated. NYX-068/071/073 identified household host-detail prompts reaching model dispatch without source reads; NYX-069/072/074 add no-dispatch denials. NYX-076 closed the selected-package doctor false-PASS; NYX-078/079 verified profile identity and decoy-process cases. NYX-080/081 found and closed rollout command, package parity, install-marker, and installed-view gaps. NYX-082 found no reproducible stale-cache promotion or unrelated-source suppression in synthetic coverage. NYX-083–089 iteratively strengthened the canonical-installer runbook across staged SearXNG writes, optional Agent Zero state, recursive metadata, secrets, ACLs, networks, systemd, runtime accounts, Grocy MCP setup, and alias paths; NYX-089 found no remaining P1/P2 gap. Private-infra independent recovery and external custody remain owner-gated.

**Runtime truth:** strict-host-key read-only probe at 2026-10-05 10:35 UTC reported Hermes active with metadata `b102dfd`; its active generated adapter differed from candidate source and lacked several candidate modules, while process environment markers were absent. This is historical evidence pending a fresh pre-rollout inspection. Protected values were not read. Current service health, source/runtime parity, and owner/household UI behavior remain unverified. No infrastructure source access, ACL, host, network, or driver changes were made.

**Next exact actions:** perform fresh read-only runtime inspection and evaluate every runbook precondition. Stop before install if any precondition fails, especially private infra provenance, secret/key parity, optional Agent Zero absence, metadata no-op checks, Compose dry-run, and exact source checkout. If all pass, use protected backups and the authorized rollout, then verify process/profile/package parity, installed artifacts, marker, provenance, doctor, validator, health, and fresh owner/household UI behavior. Keep the private checkout untouched; recovery/custody remains owner-gated.

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
