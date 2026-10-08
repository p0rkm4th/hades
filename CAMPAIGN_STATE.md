# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## HADES Core usability reset checkpoint — 2026-10-08

**Repository:** `origin/main` remains `627b7c5fc4fa875bdab78abc25133897b50a882d`. The review branch `codex/workspace-usability-20261008` is at `8bfb47eb148cb2172b6486aa3d5890074400fc19`; SSH push and remote parity pass. Benchmark/corpus commit `e6d7d395a602871c95223ee8a44b55fd63e4be87` Public CI run [37862041613](https://github.com/p0rkm4th/hades/actions/runs/37862041613) passed. The upstream-refresh docs commit has exact-SHA Public CI run [37862120331](https://github.com/p0rkm4th/hades/actions/runs/37862120331) in progress. Production was not changed.

**PLAIN STACK and HADES versions:** the control uses staged Hermes 0.21.6 without the HADES overlay, Ollama 0.40.1, and Qwen3.6 35B Q4_K_M at verified 65,536 context. HADES production contracts remain Open WebUI 0.11.1 and Hermes 0.21.2; candidate comparisons use the same Hermes/Ollama/model stack as PLAIN, adding only the HADES overlay. The Oct. 8 official-release API check confirms Open WebUI 0.11.4, Hermes 0.21.6, Ollama 0.40.1, and Hindsight 0.10.3 as current stable. Their production promotion remains held pending migration, authenticated UI, memory, rollback, and owner gates; see `docs/hades-core-upstream-refresh-2026-10-08.md`.

**Corpus and comparative evidence:** the seeded owner-pattern corpus has 55 paraphrased cases across 13 categories. Twenty-six have direct synthetic replay evidence; 29 are unreplayed; owner preference labels remain zero. The five-repeat ordinary-chat core-4 comparison completed 30 turns per stack with zero tools/schemas; paired median deltas were +2 ms HADES TTFT and −2 ms total time. It does not assess answer quality or owner preference. The clean coding escalation comparison is two repeats: PLAIN median 26.73 s, HADES 44.08 s. HADES kept both diagnosis turns read-only; PLAIN edited during diagnosis in both samples. Both arms passed four independent tests. HADES' action loop and extra model/tool turns are the current usability bottleneck. Preserve the explicit action boundary while reducing its loop cost.

**Upstream convergence:** Open WebUI 0.11.4 native Channels model streaming and persistence passed without the production 0.11.1 compatibility patch in staging; keep the production patch until production image promotion. Hermes 0.21.6 and Hindsight 0.10.3 remain staging candidates; production pins are unchanged. Ollama 0.40.1 is the staged comparison runtime, while deployed runtime provenance is not yet freshly verified. The broader component audit remains incomplete.

**Next exact actions:** verify run 37862120331; publish focused workspace escalation evidence and investigate invalid diagnosis tool attempts/action-turn overhead; extend paired replay beyond ordinary chat and the single coding fixture; finish the dependency audit; then run authenticated owner dogfood. Do not qualify the usability baseline until preference and deployed-source parity gates are evidenced.

## Prior homelab checkpoint — 2026-10-06 UTC

**Repository:** code-bearing `main` is `381543b0af21c1e1abcbf90642eb8b586f553d62`, fast-forwarded from `0cba8008a5fd0ed1a6ea1b2633379490f6cec7d8` after NYX-007 review ACCEPT and candidate Public CI [37398017938](https://github.com/p0rkm4th/hades/actions/runs/37398017938) passed. Post-promotion main CI [37398145659](https://github.com/p0rkm4th/hades/actions/runs/37398145659) passed. The change extracts bounded Proxmox archived-task page reads shared by backup and recent-activity views; credentials, transport, source configuration, and effective `VM.Audit` scope calculation remain in the adapter. Unknown/empty scope performs no task reads; task rows are field-allowlisted. The exact clean 17-module package composed from the candidate includes/imports the provider.

**Lineage:** the old local parity tip is `345cb1b6de5f9f51ad98986c88ab9f0693461921`, with merge base `b903ad331dc0269becf46600bf29db8931707fef`; its remote ref is absent and recorded CI [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701) failed public-history safety. NYX-001's capability-level review found no safe required read behavior missing from current main. Its host setup helper is a distinct deployment convenience and was not imported. The old line remains quarantined; no history rewrite or wholesale merge occurred.

**Architecture:** NYX-002 accepted extraction of pure service-monitor response handling from `hermes/sitecustomize.py` into `integrations/homelab_views.py`; Hermes retains owner-scope denial and target classification. NYX-006 accepted the NetBox recent-activity provider; configuration and bounded transport remain in the adapter wrapper. NYX-007 accepted the bounded Proxmox archived-task provider; task scope remains computed by `proxmox_visibility.py` in the server. Direct contracts cover fail-closed scope, selected/excluded IDs, 9-digit backup versus 20-digit activity IDs, capped pages/nodes, allowlisted fields, partial node outages, and retained established backup/activity behavior. Focused provider, adapter, package, authority, tree-safety, and introduced-history checks pass. Current metrics: `sitecustomize.py` 12,344 lines / 150 top-level / 217 total functions; `homelab_views.py` 916 lines / 14 top-level / 19 total; read-only adapter `server.py` 1,668 lines / 33 top-level / 35 total; `proxmox_tasks.py` 221 lines / 4 top-level / 5 total; `netbox_activity.py` 133 lines / 1 top-level / 1 total; `source_utils.py` 37 lines / 3 top-level / 3 total.

**Live truth and gates:** the homelab capability remains **PARTIAL**. Synthetic reliability contracts pass, but fresh authenticated current-source owner/household acceptance and deployed parity are unverified. NYX-124 found no verified exact active-overlay base or reusable protected runtime host-key profile; production remains unchanged. The active adapter/profile/overlay as a complete set and loaded Python bytes are not source-bound. Network trends, guest OS state, filesystem utilization, and restoreability remain capability gaps unless verified through their canonical sources. No P0/P1 defect was found in the checks run for this slice.

**Recovery custody:** the owner says there is no off-site backup; the destination/recipient remains unspecified. No artifact, checksum, or restore proof exists. No private data was sent or recovery artifact invented.

**Next exact action:** verify post-promotion CI, record the provider extraction and CI result, then continue read-only runtime provenance investigation from the protected operator record. Keep production unchanged until a trusted host-key profile and byte-verified active-overlay base permit truthful source/runtime acceptance.

## Historical code and dogfood checkpoints — superseded by the current checkpoint above



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
