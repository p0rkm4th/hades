# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Public `main` is `b3346706f5ba28fb579c1aa49e09c4ade7308169`. The code
baseline `d01d83b42bb4f00af4b2150ae3db30f440aedbc3` passed candidate run
[37327240635](https://github.com/p0rkm4th/hades/actions/runs/37327240635)
and post-promotion run
[37327487140](https://github.com/p0rkm4th/hades/actions/runs/37327487140).
Documentation commit `b3346706` reconciles live-acceptance and source-parity
claims; candidate run
[37328247716](https://github.com/p0rkm4th/hades/actions/runs/37328247716)
and post-promotion run
[37328612554](https://github.com/p0rkm4th/hades/actions/runs/37328612554)
passed. The implementation is a current-main descendant; the unsafe historic
GPU-parity branch was not imported or rewritten. Its old tip remains reference
material only.

The host-load response extraction moved two pure renderer bodies into
`integrations/homelab_views.py`, preserving Hermes wrappers, owner authorization,
source reads, and routing. NYX-003 found no P1/P2 issue. NYX-004 found no
remaining low-risk adapter projection to extract because the sizable remaining
Proxmox projections contain scope, identity, freshness, and truncation rules.
The linked NetBox alias case now has a direct full-output assertion after
NYX-005 review.

NYX-006/007 found missing and malformed Kuma observation-time test coverage.
The tests now exercise `heartbeatList` normalization through reconciliation
and require status `up` with freshness `UNKNOWN` for invalid/missing times. The
owner answer refuses to call the check currently up and omits malformed text
from timestamp wording, while the bounded source result retains it for
operator diagnostics. NYX-008 found no issue. Focused adapter, service-health,
Hermes task-chat runtime, public-tree safety, and Python compile checks pass.
No live behavior was changed or deployed in this epoch.

Current size observations after extraction: `hermes/sitecustomize.py` is
12,661 lines / 217 AST functions / 174 `_hades_*` functions;
`integrations/homelab_views.py` is 424 lines / 10 functions;
`integrations/homelab-readonly/server.py` remains 1,919 lines / 40 functions.
Keep this read adapter as the source/orchestration layer until a projection can
consume already-resolved scope, identity, and freshness facts.

The last protected production provenance is dated 2026-10-05 and is recorded
in private operator evidence. It showed an active Hermes process, but its
running homelab MCP server was older than current main; current-main byte parity
and fresh authenticated owner/household acceptance were not established. The
existing owner and Household A/B sign-in inputs returned HTTP 400; they were
not retried or reset. No current deployment or live owner dogfood is claimed.

Private infrastructure recovery remains owner-managed: the checkout is dirty,
there is no independent off-host recovery destination, and no encrypted
recipient was specified. Same-disk copies are not independent recovery. No
private topology, credentials, or raw acceptance transcripts belong in public
HADES.

**Next exact action:** inspect the documented read-only source path and current
readiness without changing host/source configuration; if authenticated UI
acceptance still cannot use an existing protected input, record the precise
gate and continue closing source-freshness/partial-outage contracts. Do not
call this campaign complete while live source composition, representative
owner dogfood, and provenance parity remain open.

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
