# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current authoritative checkpoint — 2026-10-05 UTC

**Live reconciliation for this Aster epoch:** latest main docs checkpoint is
`ab036347e7e7f2b5328d7a88ff5ea0538f591695`; its Public CI run
[37325519564](https://github.com/p0rkm4th/hades/actions/runs/37325519564)
passed. Main contains the code promotion
`8f3209757f4c2cd4170bab9829285021f45b728b`, a fast-forward descendant of
`4859acef7af95ff4611af83e8e1777a4fe355f6b`. Implementation commit
`9e11ff92f503fefeaaf24b30c478857bdd1b29f4` (`Extract pure Proxmox host-load
views`) passed candidate Public CI run
[37324585706](https://github.com/p0rkm4th/hades/actions/runs/37324585706);
the full code+docs commit passed run
[37324964236](https://github.com/p0rkm4th/hades/actions/runs/37324964236).
Post-promotion CI run [37325121388](https://github.com/p0rkm4th/hades/actions/runs/37325121388)
passed. The promoted change is not deployed. Local public-tree safety, the homelab service-health contract,
and the Hermes task-chat runtime contract pass. NYX-003 reviewed the change
and found no P1/P2 issue. Two pure host-load renderers now live in
`integrations/homelab_views.py`; small Hermes compatibility wrappers preserve
the route. Authentication, source reads, and authorization remain in
`hermes/sitecustomize.py`. The runtime test now correctly requires uncertainty
when Proxmox guest visibility is partial. This is an architectural extraction,
not a live homelab acceptance or deployment claim.

NYX-004 reviewed remaining `server.py` projections and found no worthwhile
low-risk extraction: the sizable Proxmox projections carry visibility,
identity, freshness, and truncation semantics, while smaller pure helpers do
not materially reduce concentration. NYX-005 found one test gap in the linked
NetBox-alias renderer path. A direct full-output assertion has been added
locally and the focused service-health contract passes; this follow-up is not
yet committed or in CI.

The current-main public integration worktree is clean; the
protected private infrastructure checkout remains heavily dirty and has no
independent off-host recovery destination. The owner confirms no off-site
backup is configured and has not specified an encrypted target. Same-disk
copies are not independent recovery. No private files or transcripts are
included in public HADES.

Homelab code checkpoint `8ae97d13c9b31db715e56c6c2b622ff40ae0ff82`; Public CI run [37321354100](https://github.com/p0rkm4th/hades/actions/runs/37321354100) passed. It contains the Proxmox backup and recent-activity presentation extractions and sanitized documentation. NYX-002 and NYX-004 reviews found no material P1/P2 gaps; focused direct-view and adapter-parity checks pass. The adapter outage regression now sequences a successful Kuma read followed by a Kuma failure while Proxmox changes the guest from running to stopped; it asserts a second Proxmox fetch and that no prior Kuma availability is reused. NYX-011 reviewed the test; the focused adapter script and Public CI pass. Public CI also enforces that the household named-host guard returns before direct homelab read routes, including a synthetic regression for a read inserted inside the guard. The old `codex/gpu-telemetry-parity-20261004` branch remains a source reference at `345cb1b6de5f9f51ad98986c88ab9f0693461921`, merge base `b903ad331dc0269becf46600bf29db8931707fef`; its latest Public CI run [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701) failed the public-history safety check. No old-branch history or code has been imported. NYX-001 compared both branch tips and is **ACCEPTED**: current-tree safety passes on both, but the old introduced history fails its public-history audit. The old branch adds no safe unique capability to current `main`; it regresses NetBox pagination completeness, Kuma observation timestamps, partial-source service-health handling, and inference freshness/count wording. NYX-005 confirmed current main has a partial Hermes-facing presenter extraction at `integrations/homelab_views.py` and adapter views under `integrations/homelab-readonly/`; the old branch has neither. Do not merge or port it.

Current-main concentration after the host-view extraction is measured at 12,661 lines / 217 AST function nodes in `hermes/sitecustomize.py` (174 `_hades_*`-named nodes), 1,919 lines / 40 in `integrations/homelab-readonly/server.py`, 375 / 6 in `integrations/homelab-readonly/reconcile.py`, 156 / 11 in `integrations/homelab-readonly/config.py`, 946 / 6 in `integrations/homelab-readonly/inference_view.py`, and 424 / 10 in `integrations/homelab_views.py`. `backup_view.py` is extracted at 118 lines / 1 function and `activity_view.py` at 90 lines / 1 function. These are size observations, not architecture goals.

Fresh read-only inspection on 2026-10-05 verified the production Hermes service active with zero restarts and confirmed its process selects the configured overlay. Its bytes match the protected deployment record and deterministic per-slice builder in private infra. The running homelab MCP server bytes map to public HADES commit `6bc6063702f73665a9cf666ca14cf7057d5924e`, not the current refactored `server.py`; current-main view refactors remain undeployed. This is source-lineage evidence, not byte parity with current main or fresh behavioral acceptance. Public `verify-live-hermes-overlay.sh` still verifies exact-file equality; `write-deployed-provenance.py` records selected runtime identity but does not prove the full private composition chain. The existing protected owner and Household A/B sign-in inputs returned HTTP 400; no alternate passwords or account resets were attempted. Do not use the full installer to preserve deployment-local policy. No deployment, host, network, driver, source-ACL, or backup mutation occurred. Fresh owner/household UI acceptance, live failure/conflict behavior, service health/placement, network trends, and full restoreability remain open.

Private-infra recovery remains an owner-managed limitation: the checkout is dirty, and independent encrypted off-host custody and restore proof are not established. The owner confirms there is no off-site backup and accepts that current condition. No local copy will be described as independent recovery.

**Repository state:** public `origin/main` is canonical. The dirty primary checkout and old parallel worktrees are preserved; this integration branch is the only active Aster implementation line. No private topology, credentials, or raw acceptance transcripts belong in public docs.

**Next exact actions:** commit and run Public CI on the NYX-005 direct-output assertion, fast-forward only if `main` remains at its reconciled base, and verify post-promotion CI. Keep the read layer **PARTIAL**: obtain fresh authenticated owner/household acceptance and establish reproducible current-main runtime composition before any deployment. Do not attempt private recovery transfer until the owner supplies an independent encrypted destination and public recipient.

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
