# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05

Latest validated source `main` is `4c423bf3d66437888599d175581b4ae317ae0d66`; Public CI run `37252027393` passed. This status records the source baseline and current campaign evidence. The prior inference-view extraction and the pure homelab-view extraction are promoted. NYX-001 through NYX-005 are accepted; NYX-006 differential analysis and NYX-007 portability classification are complete. NYX-008 is reviewing the false-clear and monitor-summary fixes. The old GPU-telemetry branch remains review-only; no code or history from it was imported.

The inference-view extraction is deployed with the reviewed adapter/view files, mode `0640 scotty:hades-runtime`; Hermes was healthy after one restart. Seven fresh owner/household chats passed for inference/GPU/activity and privacy boundaries. The later homelab-view extraction is included in source, installer, validator, doctor, and runtime digest checks, but is not deployed. A protected active-overlay comparison found deployment-local routes and richer source diagnostics; do not replace or partially cherry-pick the active overlay before compatibility is reconciled.

Fresh authenticated dogfood on the current deployment asked the owner how homelab freshness is established. The answer named the intended inventory, runtime, and availability source categories and included explicit time language. A fresh Household A request for internal system names and addresses was denied and redirected to approved household service checks; the private-topology guard found no leak. Both turns completed without error. Full responses remain in a mode-0600 protected report. This is targeted evidence, not a broad stale/outage soak.

NYX-006's private synthetic differential harness found that promoted source could report no conflicts when comparisons were unavailable and omitted some active partial-scope, unlinked-identity, source-time, named-monitor truncation/source, and bounded reachability caveats. It confirmed the active four-argument monitor contract and route order differ. NYX-007 classified conflict completeness and monitor unknowns as generic contracts; exact wording as an owner copy choice; effective-permission collection and Agent Zero endpoint details as deployment-local or owner-gated. Tracked source already has a generic owner-only effective-permission guest-visibility response; active route/dispatch parity remains to be checked.

A P1 false-clear in the generic conflict response was fixed in `efbcb19c`: unavailable or malformed source/conflict data now remains unknown, and partial guest visibility is stated alongside any known disagreements. Commit `4c423bf3` aligns named service-health routing with the compact canonical availability summary, supports the active four-argument call, and preserves unknown when monitor sources, identity links, or coverage are incomplete. Focused service-health contracts and Public CI pass. No runtime change was deployed. Remaining work includes Nyx's independent review, active caller/route reconciliation, live stale/partial/contradiction dogfood, native application health/placement, network trends, backup artifact/restoreability, and ordinary-user outage acceptance. Private snapshot restore is on the same `/home` filesystem; independent-device/off-host custody remains open. The homelab campaign remains **PARTIAL**.

Next exact action: complete NYX-008's read-only review of `4c423bf3`, then use it to continue the smallest generic named-monitor UNKNOWN/truncation work and assess whether a safely composable active overlay candidate exists.

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
