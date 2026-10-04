# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-04

Canonical public `main` is `c16071a54fdc750fb939a47b1bad0fcea5308e3e`; Public CI run `37243849629` passed. Aster's short-lived integration branch `codex/inference-read-freshness-20261004` is at candidate `cd7a551bb617ecf3fb7dadae04ef53762909a173`, a direct descendant of that main. Candidate Public CI run `37245402704` passed. Current-tree safety and introduced-range history safety passed. The candidate moves six pure inference/GPU presentation helpers from the MCP adapter into `integrations/homelab-readonly/inference_view.py`; the six function ASTs are unchanged, and the adapter retains compatibility imports. The candidate has not been deployed.

NYX-001 is complete and accepted: the old `codex/gpu-telemetry-parity-20261004` line is review-only, not an integration base. Its behavior is already on current main or superseded by stronger current contracts; its NetBox service projection has weaker pagination/coverage handling. Its last recorded full-history CI failed with 63 private-path/network findings. No old branch code or history is imported. NYX-002 is a review-only adversarial audit of the inference-view extraction and is pending.

Last recorded read-only runtime provenance (2026-10-04): the composed Hermes overlay SHA-256 is `1e731bee9385d8f918ddceadb374796b5c730e52f0adae38e6dc758d7f777f91`, mode `0640`; the active adapter SHA-256 is `fe7dadebebe2345793c757ad5d3475bfbc0dbe0c9df93419c7a72ca2405d6e21`, matching the pre-extraction `server.py` at `c16071a`. The candidate adapter is not active. No infrastructure, source-permission, network, host, or driver writes were made.

Current measured concentration: `hermes/sitecustomize.py` 12,887 lines, 218 AST function nodes, 173 `_hades*` functions, including 50 homelab-named functions; the homelab MCP adapter is now 2,098 lines and 40 function nodes, with 946 lines in the new six-function pure view module. The adapter extraction is source-only and awaiting adversarial review and deployed owner/household acceptance.

The homelab campaign remains **PARTIAL**. Synthetic freshness, partial-source, identity, conflict, service-health, backup-claim, inference/GPU, household-privacy, and runtime-registry contracts pass. Remaining evidence includes deployed stale/partial-source and contradiction dogfood, service-native health/placement, network trends, backup artifact/restoreability, and ordinary-user outage acceptance. The encrypted private-infra snapshot was restored and verified for bytes and modes, but resides on the same `/home` filesystem; independent-device/off-host custody remains open.

Next exact action: receive and disposition NYX-002; if no material regression is found, complete the hash-guarded adapter rollout and fresh owner/household acceptance, then promote the qualified current-main descendant. Continue one bounded extraction at a time and keep `main` green.

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
