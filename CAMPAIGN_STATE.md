# HADES campaign state

This public continuation record describes repository work only. Live host
identity, addresses, credentials, deployment provenance, and private operational
evidence are maintained in the private infrastructure repository.

## Current engineering focus

The release-convergence baseline is complete. This campaign is improving the
read-only homelab view so it composes current canonical inventory, runtime,
availability, inference, and backup sources without inventing a second source
of truth.

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
- Fresh owner dogfood of “What is running on Alexandra right now?” exposed an
  intent-gate miss: the deterministic Proxmox guest-placement answer existed,
  but the prompt fell through to a progress preamble. Current-tree routing now
  recognizes the named-host workload question and returns only current guests
  attached to the verified Proxmox node, with the selected-guest visibility
  caveat. Synthetic owner/household contracts and exact-active-overlay runtime
  checks pass. Production UI acceptance and rollout remain pending; household
  output is kept generic and source-free.
- The deployed household status boundary now uses plain language for “Why is
  everything slow?” and “Are all the computers okay?” Fresh authenticated
  Household A/B chats persisted explicit limits without owner topology or
  owner-only source reads. Candidate `4c73e28` passed Public CI; the broader
  homelab source-coverage gates remain open.
- Fresh owner dogfood for “Which GPUs are free right now?” says live capacity
  cannot be verified because per-host utilization/free-VRAM telemetry is not
  connected or available. It does not infer free capacity from hardware
  inventory or empty model residency. Household A receives only the owner
  session boundary; both answers persisted. A fresh “Can the homelab handle
  another model?” read returned provider catalogs/residency but declined to
  rank a host because capability inventory is stale, live VRAM/load is absent,
  and runtime memory needs are unknown; that answer also persisted.
- A fresh owner request to verify NVIDIA drivers and GPU execution fell through
  to an unrelated web response. The current-tree fix routes owners through the
  fixed-command GPU telemetry reader plus provider inventory, and states the
  limits of each observation. Household requests receive a generic boundary
  before any source read. Public CI, synthetic runtime coverage, exact-active-
  overlay composition, and fresh authenticated owner/household UI turns pass.
  The owner answer says driver/GPU execution are unknown because host telemetry
  is unconfigured, while reporting current provider catalog/residency reads.
  Household receives only the generic owner-only boundary. The SSH telemetry
  profile remains unconfigured; no host account/key or access was activated.
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

- Proxmox guest visibility remains limited by the read token's current scope;
  unobserved guests stay unknown. Any permission expansion remains owner-gated.
- NetBox's application-service coverage is incomplete, so some intended service
  placements cannot be established. HADES must report the gap rather than infer
  placement from hostnames, IPs, or container listings.
- Fixed-command, strict-host-key GPU telemetry is implemented and tested but
  unconfigured. Current per-host utilization/free VRAM and model-fit
  recommendations remain unavailable; host account and key activation require
  separate owner approval. The owner selected preparation of the integration;
  this does not activate credentials or access on any node.
- Future activity comparison still needs a saved prior snapshot; recent task
  history is not a complete change log and host/service event sources are not
  connected. Source comparison must continue to say when identity links or
  source coverage are incomplete. Model placement
  remains unavailable until live per-host GPU telemetry and workload memory
  requirements are known.
- Current broad status can identify responding sources and partial coverage;
  comprehensive network trends, full backup contents/custody, and successful
  inference execution are not established.
- Two synthetic Household A acceptance chats from before the context-redaction
  fix were scrubbed in both the displayed assistant message and its nested
  generation output. A fresh scan of 402 household chats found no remaining
  candidates, and both updated replies were verified in the authenticated UI.
  The protected pre-edit backup and scan evidence are retained in the private
  acceptance area; these acceptance records are not public product fixtures.
- Public `main` remains green at the release-convergence baseline. Homelab
  implementation and current continuation evidence are on the review branch;
  candidate `4c73e28` passed Public CI and is deployed behind the recorded
  read-only rollback procedure, but has not been integrated into `main`.

## Repository and deployment authority

Public source contains generic code, test fixtures, and deployment-neutral
contracts. The private infrastructure repository owns topology, host IDs,
addresses, access configuration, live deployment provenance, and private
acceptance records. The owner deployment uses an explicitly reviewed read-only
source configuration and an overlay candidate with a recorded rollback.
Synthetic evidence is not live infrastructure proof. Any further production
change requires a tested candidate, explicit scope, and rollback.
