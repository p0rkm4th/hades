# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05

Canonical public `main` is `0a21667c65e30a0beeea663c76c8821ae1b4fb6a`; Public CI run `37250073029` passed. NYX-003 re-scope is implemented and NYX-004 review is **ACCEPTED**. The prior inference-view extraction and the pure homelab-view extraction are on `main`. NYX-001 lineage, NYX-002 extraction, NYX-003 re-scope, NYX-004 review, and NYX-005 compatibility audit are accepted. The old `codex/gpu-telemetry-parity-20261004` branch remains review-only; no code or history from it was imported.

The promoted change extracts six pure inference/GPU presentation helpers from the MCP adapter into `integrations/homelab-readonly/inference_view.py`. Their ASTs are unchanged, all six old module names remain available as compatibility aliases, and Nyx confirmed the helper module has no IO/config/provider dependencies. The source was deployed to the protected runtime with hash-guarded root-only rollback. Current deployed adapter SHA-256 is `3c14a4bd22d4da57f773365860ecb24d7823360470bf0601ec65c52889d5e659` and view SHA-256 is `90cfb99901ab1c8b0cfd994eec88ebf730940f1dc7ee445d8533e9167d011a00`, both mode `0640` with the HADES runtime owner/group. Hermes was restarted once and the configured health endpoint returned HTTP 200. The Hermes overlay was not changed. Runtime behavior was dogfooded on the deployed candidate before promotion; no new runtime change followed promotion.

Fresh authenticated UI dogfood after deployment completed seven new chats with zero errors: four owner prompts exercised node activity, model location/residency, GPU identity, and per-device availability; three household prompts exercised broad status, a named-host denial, and owner-only model placement. All household topology leak checks were false. A mode-`0600` private report records the detailed result; no raw transcript is public. This is a targeted extraction acceptance, not the full homelab soak.

NYX-003 found the availability grouping helper is also used by a household-safe route. Promoted commit `9c832440` moves that classifier and four pure renderers into `integrations/homelab_views.py`; same-name wrappers retain the hook call sites, and all identity gates, route order, and dispatch remain in `sitecustomize.py`. The module is included in the Hermes overlay install and source/runtime digest, with manifest order checked against installer, doctor, and validator. Five extracted function ASTs match main exactly. The service-health contract pins byte-for-byte outputs from an unrelated working directory and checks that household requests do not invoke owner renderers. Candidate and post-promotion Public CI pass; NYX-004 accepted. The source change is not deployed: a fresh read-only check confirms the existing Hermes runtime remains active and healthy with no restart, and the new view module is absent from that runtime. The active overlay is deployment-local and its helper behavior differs from public source, so the protected compatibility review remains a prerequisite to composing a runtime candidate.

Measured concentration: parent `hermes/sitecustomize.py` was 12,887 lines / 216 AST function nodes; current `main` is 12,718 lines / 217 function nodes. The extraction removes 213 lines of presentation bodies and adds thin wrappers plus a loader. The homelab MCP adapter remains 2,098 lines / 40 functions; the separate inference view remains 946 lines / 6 functions. No owner-view response change is intended.

The homelab campaign remains **PARTIAL**. Synthetic source freshness, partial-source, identity, conflict, service-health, backup-claim, inference/GPU, household-privacy, and runtime-registry contracts pass. Open evidence includes deployed stale/partial-source and contradiction dogfood, native service-health/placement, network trends, backup artifact/restoreability, and ordinary-user outage acceptance. Private HADES-infra snapshot restore is verified for bytes/modes, but its storage is on the same `/home` filesystem; independent-device/off-host custody remains open. No P0/P1 defect was found in this slice; the unsafe old history stays quarantined.

NYX-003 re-scope and the pure homelab-view extraction are promoted; current source and documentation main `0a21667c` passes Public CI `37250073029`. Nyx-4's read-only NYX-005 audit recommends **RE-SCOPE before runtime composition**: active conflict reporting includes partial scope/source failures and freshness; an active permission-visibility route has no source equivalent; the service-monitor contract and direct-reader route order also differ. Do not overwrite these semantics. NYX-006 is a private synthetic differential harness, now assigned. Next exact action: review its mismatch matrix and identify the smallest tracked-source re-scope, then continue live-source freshness, partial-outage, and household dogfood. The new homelab view module is not deployed. The broader homelab campaign remains PARTIAL.

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
