# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Public `main` is `b17ce8e733d777ae7e0c7a7d5af15a1948671ae9`; full Public CI run [37252630983](https://github.com/p0rkm4th/hades/actions/runs/37252630983) passed. Aster integration branch `codex/aster-homelab-checkpoint-redacted-20261004` is based on that `main`; current clean-lineage documentation candidate `d3b14c53980402dce05bb66d984c1aebb23da3e4` passed full Public CI run [37254383967](https://github.com/p0rkm4th/hades/actions/runs/37254383967). It has not been promoted or deployed. NYX-012 is rechecking the corrected candidate. The old `codex/gpu-telemetry-parity-20261004` reference remains review-only at `345cb1b6de5f9f51ad98986c88ab9f0693461921`; it has not been merged or fast-forwarded. NYX-010 revalidated NYX-001 against current `main`: no semantic disposition changed, and no old-branch code/history is recommended for import.

The current source preserves Uptime Kuma's monitor `last_updated` as `availability_summary[].observed_at`. The named-monitor response presents that value as the last observation timestamp and keeps freshness separate. Focused adapter and service-health contracts pass, and Public CI is green. This source checkpoint has not been deployed; the active runtime remains a separately composed overlay. Existing protected records contain the last inspected runtime hashes and rollback details. No current-turn deployment or restart was performed.

The prior inference-view extraction remains deployed according to the last protected rollout record, with its targeted owner/household checks. The later pure `homelab_views.py` extraction is in source and reconstruction/runtime digest checks but is not deployed. The deployment-local active overlay has additional source diagnostics and routing; do not replace it wholesale. NYX-008 accepted the source-level conflict/monitor review at `b17ce8e7`; it was static review, not runtime dogfood. NYX-010 found the old-branch disposition unchanged and measured current concentration at 12,804 lines / 219 function nodes in `sitecustomize.py`, 2,099 lines / 40 function nodes in the adapter, and 266 lines / 6 function nodes in `homelab_views.py`. It recommends a bounded pure backup formatter extraction as a low-risk next adapter seam; identity/scope/dispatch extraction remains high-risk. NYX-009 completed a fresh read-only backup metadata pass. Aster applied NYX-011’s requested removal of an unnecessary protected-custody detail from the public checkpoint; the corrected clean-lineage candidate passed CI. Details and private observations remain in the protected coordination record.

The earlier owner dogfood found an empty expected-service catalog and 11 responding probes, without claiming application readiness; a separate bounded change-history response explicitly lacked a previous snapshot and omitted OS/package/driver/in-guest changes. A Household A request for internal infrastructure names and addresses was denied without topology leakage. These are dated, bounded acceptance results; they do not establish current source/runtime parity or close live outage, contradiction, service-native health, network trend, or backup-restoreability gaps. The homelab campaign remains **PARTIAL**. NYX-009 found recent completed scheduled guest-backup tasks successful through Oct 4, with the next local runs still pending at the observation time. A separately scheduled application archive completed successfully on Oct 5 UTC; its sidecar matched and the embedded database archive passed structural listing, but no full application restore was proven. Synthetic file-level dataset restore and several prior stopped-clone restore checks exist. All observed copies remain inside one homelab failure domain; independent-device/off-host custody and several application restores remain unproven.

**Repository state:** public `origin/main` is the canonical source. The primary local checkout is dirty and its local `main` diverges from public `main`; it is preserved and is not an integration base. This checkpoint is being prepared in a clean short-lived worktree from public `main`. No private topology or acceptance transcripts belong in this file.

**Next exact actions:** complete NYX-012 recheck of the corrected clean-lineage candidate, then qualify and fast-forward the docs checkpoint with Public CI on `main`; read backup metadata again after the scheduled local runs; recheck active runtime provenance before any deployment decision; then take the smallest evidence-backed adapter extraction or source-completeness fix. Keep runtime unchanged until exact overlay compatibility is established. Promote the documentation checkpoint only after review and green CI on the candidate and on `main`.

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
