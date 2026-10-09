# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## HADES Core usability reset checkpoint — 2026-10-09

**Repository:** `origin/main` remains `627b7c5fc4fa875bdab78abc25133897b50a882d`; production remains unchanged. Review branch `codex/workspace-usability-20261008` is published on GitHub. The latest committed slice is `94478968bf18daf1fb6b507c8cf417cd60f90b21` (profile automatic Hindsight recall modes); exact-SHA Public CI passed in [run 37938050594](https://github.com/p0rkm4th/hades/actions/runs/37938050594). The prior code slice `665ae23f6c881b3a5112bcee49519694d1b60e8e` (fix immediate Hindsight explicit-memory recall) also passed exact-SHA Public CI in [run 37936505960](https://github.com/p0rkm4th/hades/actions/runs/37936505960). The previous native diff-review interpretation correction is in [commit fd548444](https://github.com/p0rkm4th/hades/commit/fd548444bff808db5fdc077789a3bfdb9dd92b62); the current agentic workflow replay uses source revision `3d83370838bed1a3f25dba2514f8439ed543b2b4`. The latest code-bearing Open WebUI revocation change is `54cef506823bafcca7386e7a809f5a4cc05c5254`; exact-SHA Public CI passed in [run 37922534229](https://github.com/p0rkm4th/hades/actions/runs/37922534229). Production version contract still identifies Open WebUI 0.11.1 and Hermes 0.21.2; deployed source/runtime provenance was not freshly reverified for this slice.

Prior memory qualification at `eb6a8a5d23bea90c17264a2a5a0db0784eda25a1` also passed exact-SHA Public CI in [run 37932665004](https://github.com/p0rkm4th/hades/actions/runs/37932665004). Neither commit promotes candidates to `main` or production. Memory usability remains a release gate.

**PLAIN STACK and HADES:** comparative candidates use Hermes 0.21.6 source commit `818c13be1dc4fd28987e1e881a9408224afd4535` without the HADES overlay, Ollama 0.40.2, Qwen3.6 35B Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, and verified 65,536 context. HADES adds its overlay and catalogued Hindsight provider. Official release APIs were rechecked: Open WebUI 0.11.4, Hermes 0.21.6, Ollama 0.40.2, and Hindsight 0.10.3 remain newest stable for those repositories. Candidates have not been promoted.

**Corpus and usability evidence:** 55 sanitized owner-pattern cases cover 13 categories. The 55-case corpus has synthetic comparative evidence for 28 cases; 27 have no direct replay and owner preference labels are zero. Five-repeat ordinary-chat medians on the matched Ollama 0.40.2 run met latency targets (TTFT 1.033 s PLAIN / 1.049 s HADES; total 1.989 s / 1.752 s), but response quality and preference were not reviewed. An independent repeat of the same 48-turn conversation slice found HADES 11 ms slower at median TTFT and 15 ms slower at median total time, again with zero tools. A current-source two-pair Hermes 0.21.6/Ollama 0.40.2 coding workflow completed focused tests and clean source-only commits in both stacks; HADES median was 53.60 s versus 57.05 s PLAIN, with 2 fewer median model generations and 2 fewer tool results. HADES supplied authenticated native diff evidence in the dedicated review turns and also ran explicit `git diff` commands in other stages; whether the generated review was useful and whether those extra commands were redundant remain unreviewed. This is narrow synthetic evidence, not owner preference or a general speed claim. A current matched “Why is this Python test failing?” → “Fix it.” replay covered core-43/44: PLAIN changed the workspace during both diagnosis-only turns and then did nothing after the fix request; HADES waited, then patched and tested in 2/2. HADES was slower end to end because the stacks performed different work; answer quality and owner preference remain unreviewed. Prompt-only guidance, diff injection, and review-schema hiding candidates were rejected; preserve visible review schemas and the empty read-only execution allowlist. Direct Scotty dogfood and full-corpus review remain open.

**Multi-user staging:** disposable Open WebUI 0.11.4 acceptance covers authenticated Alpha/Beta accounts, private chats, persistence, shared Channels, LDAP group removal on fresh login, and account/session revocation. Authenticated Hindsight retain/correction/recall isolation also passed. A newly tracked, opt-in fail-closed revocation adapter passed source contracts for 0.11.1 and 0.11.4 shapes plus live disposable HTTP, sign-out, Socket.IO disconnect, Valkey outage, AOF restart, and retry checks. Candidate details and limitations are in `docs/hades-core-upstream-refresh-2026-10-08.md`. This does not qualify production Valkey persistence, multi-replica behavior, external build provenance, all household sharing rules, or owner experience. Production group management remains disabled.

**Current hot-path finding:** ordinary chat is close to PLAIN on matched latency and exposes no tools in the tested subset. The agentic explanation-to-fix replay shows HADES correctly waits for an explicit action request while PLAIN mutated early; HADES then completes the requested patch/test, with a longer elapsed time on this non-equivalent-work comparison. Coding workflow results are mixed: one current two-pair fixture showed HADES slightly faster and using fewer model/tool calls, while the value of generated diff-review answers and the explicit `git diff` calls outside review turns remain unreviewed and no owner preference or human answer-quality rating exists. The current workspace comparison records completion and independent verification, not naturalness. The isolated Ollama 0.40.2 server and rootless workspace daemon have been stopped after the run, and the private synthetic failure fixture was removed. Do not treat synthetic results as owner dogfood.

**Memory requalification progress:** the paired runner compares Hermes 0.21.6 native memory in PLAIN STACK with the HADES Hindsight provider and overlay, using isolated state and the same interactive model/runtime. A trusted-scope binding fix now rebuilds cached write banks and passes owner, household, and denied-scope contracts. Explicit saves preserve `retain_async=False`; automatic saves remain asynchronous. Low-value greetings and memory-answer turns are excluded from automatic retention so they do not create needless background queue work.

The sync-retain isolation probe against Hindsight 0.10.3 showed 7.5s retain while idle/no chat model, 12.5s with Qwen3.6 35B resident (and Hindsight evicted that model), and a 30.99s timeout with three asynchronous retains pending. This proves backlog alone can trigger the client timeout; GPU contention is an additional observed cost, not the sole cause. After queue pruning, isolated core-09 save measured 12.3s and the canonical owner plus explicit-tag listings both showed the saved item immediately. Recall still missed because a partial Hindsight entity label could tie the full memory text and replace its numeric value in HADES's answer. The route now prefers full canonical text on score ties. A focused regression passes, and two fresh-volume counterbalanced replays (HADES second, then first) both returned the synthetic $3,000 target on immediate and settled HADES recall with zero extra model generations/tools. HADES save was 12.7s in both; immediate recall was 28–36ms. These are two synthetic single-sample replays, not a general memory-quality or owner-preference qualification. Safe list diagnostics retain only item/match/candidate counts and error type; raw memory text is not captured.

Automatic memory remains weaker. With default concise retention and observation-only recall, a fact was not visible or recalled immediately; after a 28.4s Hindsight drain, it was visible and a fresh recall returned it in 10.1s. Upstream-supported chunks mode made the source visible immediately and reduced the drain to 17.5s, but the Hermes provider and HADES overlay both call Hindsight recall without `include_chunks=True`. The Hindsight 0.10.3 Python/API contract says raw chunks are omitted by default and documents `include_chunks=True` for plain retrieval. Thus the prior chunks-mode chat miss does not prove the source was unretrievable; it proves the measured provider path did not request the chunks. A direct API probe confirmed `include_chunks=True` returns the freshly retained synthetic fact in 23–25ms, while the HADES chat path still missed it immediately and succeeded after idle. The attempted `recall_sync=true` setting was ineffective for HADES because `sitecustomize.py` binds provider `prefetch` to `_hades_prefetch`, which directly calls `arecall`; it is invalid as evidence about native Hermes sync mode.

A separate concise-retention run set the upstream Hindsight provider's `retain_async=false`. Hermes 0.21.6 still enqueues automatic writes on its background writer thread, so this does not make them visible before the next turn. The HADES save reply took 1.43s; the immediate cross-session recall missed and took 29.78s (TTFT 29.12s), while the fact was visible by the end of that turn. After a 16.25s idle drain, recall succeeded in 10.37s. Hindsight generated with the 14B extractor for 16.28s and 25.23s and evicted the resident 35B interactive model. This one synthetic sample shows that toggling Hindsight's internal async mode does not solve the provider queue/readiness race and can still incur model contention; it is not a candidate for promotion. The focused result is in `benchmarks/hades-core-memory-automatic-retain-sync-20261009.json` and explicitly records the dirty-worktree provenance. Hindsight's official 0.10.3 configuration guide says chunks mode is a plain-retrieval/RAG profile, not a general memory-quality shortcut; do not promote it without quality and owner-use evidence. The staged Ollama process, disposable Hindsight containers/volumes, and temporary homes were cleaned up; production remains unchanged.

The first opt-in `include_chunks=true` HADES adapter trial used Hindsight's documented chunks/vector-only profile. It still missed the immediate cross-session recall (1.42s), although a direct `include_chunks=true` API probe 23.6ms after that turn returned the source marker. After a 1.02s idle drain, HADES recalled it in 2.07s. This isolates a write/index visibility race ahead of HADES prefetch; asking for chunks alone does not resolve it. The candidate adapter was removed after this failed test; the artifact remains as evidence, not as an accepted product path.

**Native prefetch tax measured:** Hermes 0.21.6's inherited queued prefetch ran three additional Hindsight recalls in the matched HADES automatic-memory sample (12.0, 33.2, and 27.7ms); every queued result had zero memories. HADES separately made its direct current-query recalls, whose diagnostic result sequence was two empty-bank `NotFoundException`s, one empty result on immediate recall, and one observation after the drain. HADES never consumes Hermes' queued result because its scoped `prefetch` override supplies the current result directly. The instance-scoped no-op for this unused queue was then replayed twice on fresh volumes in opposite stack orders: no queued recalls occurred, the direct recall sequence remained identical, immediate recall still missed, and settled recall still succeeded (10.39s and 10.08s). User-facing tool/generation counts were unchanged. This justifies removing duplicate work but does not fix automatic-memory readiness; latency differences are too noisy for a speed claim. Artifacts: `hades-core-memory-prefetch-paths-20261009.json`, `hades-core-memory-prefetch-paths-queue-disabled-20261009.json`, and `hades-core-memory-prefetch-paths-queue-disabled-hades-first-20261009.json`.

**Same-session continuity:** the benchmark now uses Hermes' authenticated `X-Hermes-Session-Id` contract and sends the fact and follow-up as separate API requests, with the server loading the transcript for turn two. Two fresh-volume replays in opposite stack orders returned the expected Denver marker in both PLAIN and HADES, with one model generation and zero tools on each follow-up. HADES follow-up elapsed times were 0.883s and 0.975s; PLAIN was 0.611s and 0.606s. HADES direct memory recall was empty during the follow-up, so this proves transcript continuity, not Hindsight memory recall; cross-session readiness remains unqualified. No queued recalls ran under the queue-removal change. Artifacts: `hades-core-memory-same-session-continuity-20261009.json` and `hades-core-memory-same-session-continuity-hades-first-20261009.json`.

**Next exact actions:** commit and qualify the same-session continuity runner and results, then continue measuring cross-session memory readiness separately. The HADES direct prefetch override bypasses upstream `prefetch_waits_for_retain`; the removed `include_chunks=true` adapter did not fix the measured race. Determine whether a bounded bank-scoped readiness check can cover cross-session recall without delaying ordinary chat. Keep the trusted-bank binding, low-value retain pruning, and entity-tie regression. Run repeated fresh-volume core-09 checks to establish reliability, and qualify automatic correction behavior. PLAIN STACK remains Hermes native memory; HADES remains Hermes plus the Hindsight provider and overlay. For core-43/44, direct Scotty review of answer quality and preference remains necessary; synthetic evidence only verifies the recorded action/verification behavior. Continue closing the 27 corpus cases without direct replay and finish dependency/deployed-provenance and household acceptance gates before promotion. Direct owner dogfood and preference evidence remain release gates. Keep main and production unchanged until coherent slices pass relevant CI and acceptance gates.

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
