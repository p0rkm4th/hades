# HADES campaign state

This public continuation record describes repository work only. Live host
identity, addresses, credentials, deployment provenance, and private operational
evidence are maintained in the private infrastructure repository.

## Current engineering focus

The release-convergence baseline is complete. This campaign is improving the
read-only homelab view so it composes current canonical inventory, runtime,
availability, inference, and backup sources without inventing a second source
of truth.

## Current verified status — 2026-10-04

- Latest pushed code candidate is `9511c75`; Public CI run `37169928930` passes.
  The immediately preceding run correctly rejected a private topology name in
  a synthetic test label; that fixture is now generic and the public-tree
  safety guard passes. Public `main` remains at `c83ddd6`.
- The owner-approved Proxmox audit-scope update is complete on both configured
  sources. Nyx-4 verified token-effective read-only VM audit, full guest
  enumeration, and no access-denial exclusions. Fresh owner UI now sees both
  Proxmox scopes as responding and complete. The broad answer remains partial
  because NetBox's intended-service catalog is empty and 15 Proxmox/Kuma
  observations lack verified cross-source identity links.
- Fresh post-scope owner summary completed in about 4.6 seconds and preserved
  those unknowns. Household A received no private topology or resource detail;
  its first broad-summary turn promised a read-only check instead of returning
  a direct boundary response. This is a household UX follow-up, not an observed
  disclosure. Raw acceptance remains in private mode-0600 evidence.
- `40054cb` remains active on VM 802 for GPU hardware-name questions. Fresh
  owner dogfood found a cluster-wide guest question was misread as a request
  about a host literally named “Proxmox”; a direct named-host question returned
  current running/stopped guests correctly. Candidate `2a35c7d` recognizes the
  cluster wording, lists running/stopped/unknown guests only from configured
  Proxmox identities, and claims a complete view only when all configured
  endpoint scopes are `ALL_GUESTS`. It includes the lowercase display-label
  correction, reports Proxmox scope-read timestamps, and closes the compound
  household-summary route that previously fell through to a model promise.
  Focused synthetic and composed runtime checks plus Public CI pass; the
  combined two-file rollout awaits owner decision. Production is unchanged by
  this candidate.
- HADES review branch `codex/homelab-protected-source-contract-20261001` is
  pushed at `348c08b`; Public CI run `37165321007` passed. Runtime candidate
  `09698a3` remains the latest recorded runtime deployment with a root-only
  hash-guarded rollback. Public `main` remains at the green release-convergence
  baseline `c83ddd6`.
- Fixed-command, non-sudo GPU telemetry is active only in the explicitly
  approved owner deployment. Fresh persisted owner dogfood reports per-device
  free VRAM/utilization for identity-linked inference endpoints, including the
  recently repaired friendly-name route. Samples are point-in-time; host CPU
  load, inference execution, and model fit remain unverified. Other deployments
  remain unconfigured and owner-gated.
- Nyx-4 verified that the configured inference endpoint IDs have explicit
  links to current NetBox devices. Owner dogfood found a remaining friendly-name
  lookup gap even when the endpoint ID was stably linked. Candidate `09698a3`
  resolves an exact provider-ID alias only through a unique linked NetBox
  identity and always responds with the canonical NetBox label; ambiguous or
  unlinked IDs remain unresolved. Fresh owner UI now returns the targeted live
  GPU sample and preserves model-fit uncertainty. Household A remains generic.
- Named-node model-capacity requests now require one stable resource identity,
  then show only that host's linked inference endpoint and GPU readings. Fresh
  owner multi-intent capacity dogfood passed with four linked-device readings
  and a no-fit-guarantee caveat; Household A/B received no host or GPU details.
- Fresh owner natural-language dogfood found that “What server has the four
  P4000s?” fell through to broad status and “How's the big GPU box doing?” fell
  through to an ungrounded fallback. Candidate `40054cb` passed Public CI run
  `37167027365` and was deployed to VM 802 with hash-guarded root-only rollback
  copies. Fresh owner UI resolved the four-P4000 question and returned
  timestamped per-card activity for “big GPU box”; it disclaimed workload
  completion. Household A received only the generic hardware boundary.
  Installed hashes, service state, file modes, and focused UI acceptance pass.
  Displayed canonical host labels remain lowercase in this path; this is a
  presentation P2.
- The live broad owner summary reports partial Proxmox guest visibility and an
  empty NetBox application-service catalog. Agent Zero’s configured endpoint
  returned a bounded HTTP response, which does not prove task execution.
- A fresh broad owner UI refresh confirms the same source gaps: source requests
  respond, but both Proxmox guest-visibility scopes remain partial/degraded,
  the NetBox application-service catalog remains empty, and 15 Proxmox/Kuma
  resources have no verified cross-source identity link. Four configured Kuma
  probes report no failures (reachability only); all three inference catalogs
  respond without proving generation or GPU capacity.
- Fresh owner backup dogfood received configured job and recent successful
  task evidence from both Proxmox sources plus enabled repository backup
  checks. Some returned tasks have no guest attribution, and task coverage is
  limited to selected guests. HADES explicitly does not claim backup-content
  integrity, off-site custody, or restoreability from this evidence.
- Fresh authenticated owner UI dogfood asked where the game server runs.
  HADES reported that the NetBox application-service catalog is empty and did
  not guess intended or current placement. Household A's fresh game-health
  answer could not confirm status from its current check and disclosed no
  owner topology. Protected response artifacts remain mode 0600.
- Paired live owner/Household A game-health dogfood found that the owner view
  could not verify a matching Kuma monitor, while the household wording implied
  an inconclusive existing check. A local candidate now says there is no
  current game-server check when no matching monitor is available, while
  preserving the separate inconclusive wording for a matching monitor with
  unknown status. Candidate `fa33f81` passed focused service-health and Hermes
  runtime contracts and Public CI. It was deployed to the approved owner
  runtime with a root-only hash-guarded rollback. Hermes is active; fresh
  owner UI identifies the missing matching Kuma monitor, and Household A now
  says it has no current game-server check without exposing owner topology.
- Follow-on candidate `9d58e64` passed Public CI and was deployed with a separate
  root-only, hash-guarded rollback. It distinguishes a missing monitor, an
  unavailable Kuma source, a stale observation, unknown observation freshness,
  and a fresh monitor with unknown status in plain household wording. Synthetic
  coverage exercises each state; fresh owner/Household A UI acceptance still
  passes with no topology disclosure.
- Fresh owner provenance dogfood asked whether Proxmox scope covers all guests
  or only a selection. Candidate `19af4b6` now reports complete, selected,
  mixed, no-audit, or unknown scope from the adapter's effective-permission
  result and distinguishes that source from the returned guest list. Synthetic
  scope cases, route tests, and Public CI pass. It is deployed with a separate
  root-only, hash-guarded rollback. Fresh owner UI confirms the current scope
  is selected guests only and includes permission-read timestamps; household
  visibility is unchanged.
- “Where is HADES running?” reports two same-name Proxmox guests and separates
  the stopped guest from the running guest; it does not claim application
  health. Nyx-4 has been asked to confirm whether the stopped duplicate name is
  intentional or stale. Household A/B dogfood remains redacted.
- Fresh network-slowdown dogfood combines configured-probe response times and
  Proxmox resource samples but explicitly says packet loss, throughput, DNS
  timing, and trends are unavailable; it makes no causal diagnosis.
- Fresh natural-language dogfood on the current owner deployment asked which
  sources are verifiable and what remains unknown. The owner answer preserved
  partial guest visibility, empty intended-service coverage, unlinked records,
  and the limit of host probes. Household A's “Are all the computers okay?”
  and Household B's “Why is everything slow?” returned plain account-boundary
  answers without infrastructure details. Persisted protected evidence and
  per-turn timings are recorded in the private infrastructure note.
- A fresh owner source-conflict question found no conflicts among the records
  compared, included the source-read completion timestamp, and explicitly said
  that unlinked records and partial guest visibility prevent a lab-wide
  agreement or all-clear claim. The first capture attempt used an overly strict
  WebSocket-only completion condition and timed out; the corrected UI harness
  accepted the newly rendered completed response in 4.5 seconds. This was a
  harness correction, not a product change.
- Fresh Household A/B everyday-language dogfood asked which computer was having
  trouble and whether the AI service was usable. The first received only the
  plain home-computer boundary; the second reported responding availability
  checks without promising that a prompt would succeed. Neither answer exposed
  private infrastructure details.

The private coordination note and protected evidence paths are recorded in
`hades-infra`; no private topology, credentials, or live endpoint details
belong in this public continuation file.

## Current repository work

- Source identity is explicit. Proxmox, NetBox, and Kuma records are never
  joined by display name or address alone.
- Reviewed Proxmox source IDs, provider endpoints, identity links, and physical
  host-monitor links are active in the owner deployment. No canonical source
  was written by HADES.
- Missing identity links, duplicate mappings, source disagreement, and stale
  observations remain visible in the read model.
- Source adapters remain bounded and read-only.
- Generic natural-language node-status routing is covered by synthetic tests.
- Configured Ollama reads collect installed model catalogs and provider-reported
  residency from `/api/tags` and `/api/ps`. OpenAI-compatible `/v1/models`
  catalogs are supported without claiming loaded state. Owner UI dogfood
  confirms these reads while distinguishing residency from GPU execution or
  successful generation. Synthetic contract
  coverage includes source identity, linked NetBox display names, partial
  failure, token transport requirements, and owner response shaping.
- Model inventory questions use only configured inference sources and fetch a
  targeted NetBox record only when a model-location answer needs one; they do
  not call the broad Proxmox/Kuma summary.
- Authenticated owner dogfood covers broad status and freshness, named-node
  activity, service placement, backups, model inventory, and capacity caveats.
  Household dogfood confirms generic answers and redaction for private
  infrastructure questions. Sensitive old assistant turns are also removed
  from household model context before routing and fallback.
- The latest routed-read candidate is deployed after green Public CI with a
  root-only rollback copy. Fresh owner UI turns verified bounded recent
  activity, model-capacity uncertainty, source-coverage caveats, and scoped
  resource ranking. Household UI turns remained generic and denied owner-only
  placement and source details. This acceptance is limited to those prompts;
  it does not close the incomplete-source gaps below.
- A follow-up owner question about Agent Zero availability and task execution
  initially fell through to a generic answer despite the configured endpoint
  probe. The new route uses that bounded read-only probe and explicitly leaves
  task execution unverified; fresh owner UI dogfood confirms this, while a
  household turn remains redacted. No Agent Zero task was invoked.
- Fresh owner UI dogfood of “what's down / what can't you verify?” now reports
  empty service-catalog coverage as unknown intended placement. It labels
  current availability data as Uptime Kuma probes and distinguishes responding
  host probes from application readiness. Guest visibility and live GPU
  capacity remain open evidence gaps.
- Fresh owner dogfood of a named-host workload question exposed an intent-gate
  miss: the deterministic Proxmox guest-placement answer existed, but the prompt
  fell through to a progress preamble. Candidate `e01570c` now recognizes this
  question and returns the current visible guest with the selected-guest scope
  caveat. Public CI passed; the candidate was deployed with a root-only rollback
  copy, and fresh owner/household chats persisted the scoped answer and generic
  boundary. Application-service health remains unverified by guest inventory.
- Fresh owner dogfood of a household-app placement question confirmed the
  reachable NetBox service catalog is empty; HADES declines to guess current or
  intended placement. Its availability question found no matching current Kuma
  monitor and correctly declined to call the app healthy. Candidate `1beba11`
  now includes the Kuma source-read timestamp (or source-unavailable state) in
  this no-match answer; Public CI, exact-active-overlay composition, rollback
  deployment, and fresh persisted owner/household chats pass. The household
  placement reply contains no host or address details.
- Fresh “Is everything okay with the homelab?” owner dogfood returned a partial
  live summary rather than a false all-clear. It separated selected-guest
  visibility, empty NetBox service inventory, fresh host probes, inference
  catalogs/residency, and unresolved source links, and did not equate any of
  those with application readiness, successful generation, or GPU capacity.
  Fresh Household A dogfood returned only the generic home-computers boundary.
- Fresh owner dogfood of named inference-host activity initially combined
  provider catalog/residency, a host probe, and historical hardware inventory
  without live GPU data. Candidate `3c6504c` now fetches only the requested
  node's sample; candidate `09698a3` also resolves a uniquely linked provider
  ID used as the owner's friendly name. The latest owner UI returns the
  target-only timestamped GPU sample. Household A/B remain generic. Hardware
  role and specifications remain historical; CPU load and actual inference
  execution are not verified.
- The deployed household status boundary now uses plain language for “Why is
  everything slow?” and “Are all the computers okay?” Fresh authenticated
  Household A/B chats persisted explicit limits without owner topology or
  owner-only source reads. Candidate `4c73e28` passed Public CI; the broader
  homelab source-coverage gates remain open.
- Fresh owner dogfood for “Which GPUs are free right now?” now reports
  timestamped per-device utilization and free VRAM from the fixed-command
  reader. The answer treats it as a point-in-time observation and does not
  infer model fit from free VRAM or provider-reported residency. Household A/B
  receive only the owner-only boundary. Model placement remains uncertain
  without model, quantization, context, and runtime memory requirements.
- A fresh owner request to verify NVIDIA/GPU status is routed through the
  fixed-command telemetry reader and provider inventory. The approved
  deployment's restricted `nvidia-smi` read proves device telemetry is
  available at that check; it does not establish general driver health, GPU
  process attribution, or successful inference. Provider-reported residency
  remains separate evidence. Household A/B receive the generic boundary before
  owner source reads. The dedicated non-sudo account/key and strict-host-key
  profile are active only for the explicitly approved deployment; no driver
  changes were made.
- Fresh “What changed since yesterday?” owner dogfood returned the bounded
  Proxmox-task/NetBox-update view with a read timestamp and partial-scope
  caveats. Candidate `33b24ec` now explicitly states that host OS,
  package/driver, and in-guest service events are not in those sources;
  Household A remains limited to the private-change boundary. Both chats
  persisted after the overlay and MCP adapter were deployed together.
- Backup answers distinguish configured jobs and bounded task history from
  verified backup contents, independent custody, and restoreability.
- Current-tree privacy checks and the focused homelab contracts pass.
- A fresh capability-discovery question exposed internal source/tool descriptions
  on a household model-fallback path; another attempt stalled on a preamble. The
  affected acceptance chats were removed while protected evidence was retained.
  Candidate routing now sends this intent to the deterministic owner summary or
  the plain household boundary, and regression tests verify that no household
  model/tool invocation occurs. Public CI passed, the exact-active-overlay
  runtime contract passed, and the fix was deployed with a root-only rollback
  copy. Fresh owner and household UI chats persisted the scoped summary and
  generic boundary respectively, closing this disclosure defect. The broader
  homelab source-coverage gaps below remain open.

## Remaining evidence

- Proxmox guest visibility remains limited by the configured read tokens;
  unobserved guests stay unknown. The previously owner-approved VM.Audit scope
  still needs effective-permission verification; any broader scope remains
  gated.
- NetBox's application-service coverage is incomplete, so some intended service
  placements cannot be established. HADES must report the gap rather than infer
  placement from hostnames, IPs, or container listings.
- GPU telemetry is configured only in the approved owner deployment using a
  dedicated non-sudo identity, fixed command, and strict host-key checking.
  Other deployments remain disabled until separately configured and approved.
  Telemetry does not measure host CPU, attribute GPU use to a process, prove
  successful generation, or establish model fit.
- Future activity comparison still needs a saved prior snapshot; recent task
  history is not a complete change log and host/service event sources are not
  connected. Source comparison must continue to say when identity links or
  source coverage are incomplete. Linked-host GPU telemetry is available only
  in the approved owner deployment, but model fit remains unconfirmed without
  runtime memory requirements, context, quantization, and workload details.
- Current broad status can identify responding sources and partial coverage;
  comprehensive network trends, full backup contents/custody, and successful
  inference execution are not established.
- Two synthetic Household A acceptance chats from before the context-redaction
  fix were scrubbed in both the displayed assistant message and its nested
  generation output. A fresh scan of 402 household chats found no remaining
  candidates, and both updated replies were verified in the authenticated UI.
  The protected pre-edit backup and scan evidence are retained in the private
  acceptance area; these acceptance records are not public product fixtures.
- Fresh owner UI dogfood found “Is the game server working?” fell through to a
  broad summary even though the correct service-health unknown was available.
  Candidate `b6c9cfb` routes the plain-language alias to the Minecraft monitor
  check. Owner now sees the missing current monitor and source-read timestamp;
  Household A and B receive generic answers without infrastructure detail.
  Public CI, focused route/runtime contracts, composed overlay, rollback
  deployment, and persisted UI acceptance pass.
  Service health and placement remain unknown without canonical service
  inventory and a matching current monitor.
- A fresh owner source-comparison question returned no contradictions among
  linked records compared, while explicitly excluding unlinked records and
  partial Proxmox guest scope and disclaiming a lab-wide all-clear. Household B
  received only the generic boundary. Both chats persisted; this confirms
  partial/unknown handling and redaction, not complete source reconciliation.
- Public `main` remains green at the release-convergence baseline. Homelab
  implementation and current continuation evidence are on the review branch;
  candidate `a8fbb3a` passed Public CI and is deployed behind the recorded
  read-only rollback procedure, but has not been integrated into `main`.

## Repository and deployment authority

Public source contains generic code, test fixtures, and deployment-neutral
contracts. The private infrastructure repository owns topology, host IDs,
addresses, access configuration, live deployment provenance, and private
acceptance records. The owner deployment uses an explicitly reviewed read-only
source configuration and an overlay candidate with a recorded rollback.
Synthetic evidence is not live infrastructure proof. Any further production
change requires a tested candidate, explicit scope, and rollback.

### Latest authenticated follow-up acceptance — 2026-10-03

- Latest deployed code candidate is `4a4bfdc`; Public `main` remains `c83ddd6`.
  Public CI run `37159647718` passed. This continuation record is on a later
  documentation-only review-branch commit; the code candidate is not merged
  into `main`.
- Fresh owner UI dogfood now carries named-node activity into an evidence-based
  placement follow-up. It shows only the selected host's linked GPU sample;
  a later size follow-up and explicit named-host fit question also stay scoped
  to that identity and do not reveal provider endpoint IDs for unlinked hosts.
  Household A/B receive only the generic infrastructure boundary.
- A fresh owner diagnostic for a named inference node includes live per-device
  GPU telemetry and keeps historical hardware inventory, provider residency,
  and unmeasured CPU load distinct. The live chain and Household A/B answers
  were saved with mode `0600` outside the public repository.
- A separate whole-homelab owner query completed in about 4.4 seconds in one
  fresh UI measurement; treat this as a sample, not a latency benchmark.
- Fresh owner questions about resource use, recent change, and unverified
  services returned bounded Proxmox metrics/task history and explicit source
  gaps. Ranking is guest-scope only and partial; change history has no saved
  before/after snapshot; service probes do not establish application readiness.
  Each turn completed in about 4.4 seconds in a single UI sample.
- Two follow-up routing defects were repaired from real UI evidence: pronoun
  placement now recomputes from current linked telemetry when conversation
  context is trimmed, and the adapter filters generated named-host questions
  to that host instead of listing every endpoint. Focused adapter/runtime and
  service-health contracts pass.
- Remaining gaps are unchanged: selected-scope Proxmox visibility, empty
  NetBox application-service catalog, an unlinked physical inference endpoint,
  incomplete network trends and backup verification, and unverified successful
  inference execution. Display labels from inventory currently render in
  lowercase in some answers; this is a minor presentation issue, not an identity
  or safety failure.
