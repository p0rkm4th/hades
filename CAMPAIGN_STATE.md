# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

Canonical public `origin/main` is `32eff46359941fd8116e7c901d9e2e4a26637fb9`; source-bound overlay composition commit `d246a008a3767fcb3c79fe5a65cc411514c9c436` and documentation checkpoint `32eff46359941fd8116e7c901d9e2e4a26637fb9` are promoted. Candidate CI [37391373817](https://github.com/p0rkm4th/hades/actions/runs/37391373817) and post-promotion CI [37391590268](https://github.com/p0rkm4th/hades/actions/runs/37391590268) pass. Earlier provenance-writer baseline CI [37388632877](https://github.com/p0rkm4th/hades/actions/runs/37388632877) and [37388754814](https://github.com/p0rkm4th/hades/actions/runs/37388754814) also passed. The earlier main-promotion run [37379431810](https://github.com/p0rkm4th/hades/actions/runs/37379431810) failed only public-history audit because its range contained a private local checkout path in an earlier checkpoint commit. That value is absent from current tree; public history was not rewritten. Current-tree and later introduced-range checks pass.

The active Aster integration branch is `codex/aster-proxmox-resource-ranking-view-20261005` and currently matches `origin/main`.

The first extraction candidate `bbac828c7144988eaccb7c501ea79f43bbeb0387` failed current-tree safety in [37378812179](https://github.com/p0rkm4th/hades/actions/runs/37378812179); the correction at `71816c7fff38c3b7e86b9fe6e1316a6f97a8714e` passed [37379104048](https://github.com/p0rkm4th/hades/actions/runs/37379104048). NYX-102 accepted the pure GPU execution response-view extraction, promoted in `a91db753`. NYX-103 found a P2 partial-source gap: either tool exception previously discarded both reads. The independently-failing-safe GPU telemetry/provider correction at `bdc251bb` and checkpoint `d708246f` are on main. Candidate CI [37379792181](https://github.com/p0rkm4th/hades/actions/runs/37379792181), post-promotion main CI [37380311483](https://github.com/p0rkm4th/hades/actions/runs/37380311483), and current-main CI [37386827640](https://github.com/p0rkm4th/hades/actions/runs/37386827640) pass. It is not deployed; production runtime parity remains unverified.

The homelab read layer remains **PARTIAL** as an owner-facing live capability. The latest protected strict-key inventory found 10 active adapter modules versus 14 in current main (four absent, two byte-different); disk inspection does not prove loaded process bytes. Exact active package/profile/overlay hashes are retained in the protected operator record, but no clean source revision binds the complete set. Deployed overlay and adapter provenance remain **UNVERIFIED**. The bounded owner/household UI run passed eight prompts on the currently reachable deployment, but not current-main runtime parity. The `d5f82790` and `d246a008` source revisions have not been deployed; no source ACL changes were made for these provenance changes.

The code-bearing baseline is `d246a008a3767fcb3c79fe5a65cc411514c9c436`; it adds source-bound composition of one tracked Hermes guest-visibility wrapper to the redacted provenance-writer stdout fix, NYX-114-accepted service-placement presentation extraction, and NYX-119-accepted process-bound provenance capture. Candidate CI [37391373817](https://github.com/p0rkm4th/hades/actions/runs/37391373817) and post-promotion main CI [37391590268](https://github.com/p0rkm4th/hades/actions/runs/37391590268) pass. Earlier baseline `d5f82790` candidate/main CI [37388632877](https://github.com/p0rkm4th/hades/actions/runs/37388632877) and [37388754814](https://github.com/p0rkm4th/hades/actions/runs/37388754814) also passed. The provenance writer persists the full private record only in mode-0600 output and prints a fixed success summary. It binds argv/environment and profile/overlay disk reads to one MainPID snapshot, with stable no-follow reads and final identity checks; it explicitly reports current-disk identity, not already-loaded Python memory. `hermes/sitecustomize.py` is 12,475 lines (12,540 at the recorded pre-extraction baseline), with 150 top-level and 217 total functions. `integrations/homelab_views.py` is 776 lines with 13 top-level and 18 total functions. `integrations/homelab-readonly/server.py` remains 1,864 lines with 36 top-level and 40 total functions. The separate original HADES worktree remains dirty and divergent and is preserved. Private infrastructure recovery remains unresolved: the owner confirmed there is currently no off-site backup and could not identify an independent destination or encryption recipient; no artifact or restore proof exists. Historical private labels and a previously published local-path reference remain in public history; no rewrite was performed.

**Source-witness audit:** NYX-116/117 confirmed that the adapter composer can bind exact package bytes to clean HADES source, but the deployed package differs from current main (10 modules versus 14; four absent, two byte-different). The provenance writer hashes the selected profile and active overlay, but neither is source-bound: `hermes/config.yaml.example` is only a seed copied when no profile exists, existing profiles are preserved, and there is no tracked profile renderer or general overlay composer. The Hindsight candidate helper composes one function and reports hashes without a composition manifest. NYX-118 found two historical revisions matching only a nine-module inventory; current protected inventory has ten modules, so no complete adapter witness exists. No exact tracked overlay blob or source-bound composition record was found. Keep adapter lineage unmatched and profile/overlay at HASH_ONLY; overall deployment provenance is INCOMPLETE. NYX-119 identified and Aster fixed a P1 race that could combine unit configuration with a different Hermes PID and parse/hash different profile snapshots. The writer now captures argv/environment from one PID, binds path selection to that process environment, uses stable no-follow reads, and rechecks process/source/artifact identity before writing. Nyx re-review accepted the fix, and focused, candidate, and post-promotion CI pass. A test documents that post-start disk replacement can differ from already-imported code, so the artifact classification explicitly says current-disk identity and does not claim memory identity. Operators must serialize provenance capture with activation because a narrow concurrent-activation window remains after the final check.

NYX-122 added a function-scoped Hermes overlay composer and protected composition manifest, now on main. It replaces only the tracked guest-visibility response wrapper, records exact base/final bytes plus source revision/tree and wrapper digest, and preserves all other deployment-local overlay bytes as opaque base content. The provenance writer can verify that record against exact tracked Git blobs and stable current-disk bytes; hostile cached bytecode, Git stat-cache hiding, and concurrent source-revision movement have regression coverage. Focused tests pass locally. This does not identify the complete deployed overlay or adapter package, source-bind the selected Hermes profile, or prove in-memory loaded Python bytes. Candidate CI [37391373817](https://github.com/p0rkm4th/hades/actions/runs/37391373817) and post-promotion CI [37391590268](https://github.com/p0rkm4th/hades/actions/runs/37391590268) pass at main. Keep deployment lineage INCOMPLETE.

**Next exact action:** continue source/runtime witness work and read-only owner/household acceptance needed to distinguish current-main behavior from deployment parity. Deployment lineage remains INCOMPLETE because there is no full adapter-package witness, source-bound profile, or complete active-overlay witness. Keep the activation record explicit about current-disk identity and serialize any future capture with activation. NYX-120's read-only census found preserved unique work across clean and dirty branches/worktrees; do not delete or prune those histories. NYX-121 recommended investigating one overlay-composition manifest candidate; NYX-122 is on main and adapts only the tracked guest-visibility wrapper with exact-blob validation and race tests. Private recovery remains gated: the owner has no off-site backup and no destination/recipient to specify, so do not create a purported recovery artifact. Preserve the public-history audit finding and keep production unchanged until source lineage and acceptance are truthful.

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
