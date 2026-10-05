# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Canonical public `origin/main` is `557d0cb0c382c4d267beb5a7651bc12be70ceea8`. Its Public CI run [37375570990](https://github.com/p0rkm4th/hades/actions/runs/37375570990) completed successfully, including 122 regression/safety steps. The pushed Aster checkpoint candidate `9125026abb02574c2cb818de19867dad56483ed1`, one documentation-only commit ahead of main, passed push-triggered Public CI [37376227713](https://github.com/p0rkm4th/hades/actions/runs/37376227713). This local docs reconciliation is a newer uncommitted change and has not been qualified yet. The connected GitHub integration denied pull-request creation with HTTP 403; no promotion occurred.

Mission: keep current green main canonical, semantically recheck the quarantined homelab line, close the smallest important read-only reliability gaps, and continue bounded architecture extraction. Prior NYX-001 and current-delta NYX-101 reviews found no safe unique old-branch behavior missing from main; NYX-101 is ACCEPTED and no old commits were imported. NYX-102 independently accepted Aster's local pure GPU execution response-view extraction. It moves formatting only into `integrations/homelab_views.py`; Hermes retains scope/subject authorization and live reads. The AST is identical to the parent function, and focused output/household tests pass. This extraction and the five-doc checkpoint are uncommitted, unqualified candidate work; they are not on main or production.

The homelab read layer remains **PARTIAL** as an owner-facing live capability. The last protected strict-key inventory found the active selected adapter tree has 10 Python modules versus 14 on current main: four expected modules are absent and two files differ. Hermes was active, but selected disk-tree inspection does not prove process-loaded bytes. Deployed overlay and adapter provenance remain **UNVERIFIED**; no production deployment or canonical-source ACL mutation occurred. The bounded owner/household UI run on the currently reachable deployment passed eight fresh prompts with same-chat persistence, zero household topology leaks, and zero turn errors, but it does not prove current-main runtime parity. The public tree includes source contracts for freshness, partial-source behavior, contradictions, malformed input, and household denials.

Measured canonical main at `557d0cb0`: `hermes/sitecustomize.py` 12,540 lines / 150 top-level and 217 total functions (174 `_hades_*`); `integrations/homelab-readonly/server.py` 1,864 lines / 36 top-level and 40 total functions. The uncommitted candidate after the GPU response-view extraction measures `sitecustomize.py` at 12,469 lines and `homelab_views.py` at 737 lines / 12 top-level functions. The extraction removes 71 lines from Hermes while preserving the same 150 compatibility/routing definitions; this is a small, measurable architecture step, not a line-count target.

Private infrastructure recovery remains owner-accepted but unresolved: no independent encrypted off-site destination or recipient is available, no artifact was created, and no restore proof exists. Historical private-label matches remain in published history; no history rewrite was performed. The local `/home/scootz/Hades` worktree is heavily dirty and divergent; it is preserved and is not the integration source.

**Next exact action:** finish local qualification of the NYX-102-accepted slice and reconciled docs, commit and push the bounded candidate, then inspect the exact push-triggered Public CI. Promote only by fast-forward if the candidate is green and main remains its ancestor; verify post-promotion CI. Keep production unchanged until source/runtime provenance is truthful.

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
