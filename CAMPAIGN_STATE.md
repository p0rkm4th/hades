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

- HADES review branch `codex/homelab-protected-source-contract-20261001` is
  pushed. Public `main` remains at `c83ddd6`; its release-
  convergence CI is green. Review head `4096f39` passed Public CI run
  `37170321258`; runtime candidate `9511c75` passed run `37169928930`. Later checkpoint-only documentation commits have no separate recorded CI
  status.
- Candidate `9511c75` is not deployed. Its current composed runtime passed the
  direct Proxmox owner route for complete and partial scopes, the household
  boundary, the Hermes runtime contract, focused adapter checks, and the
  public-tree safety check. Its deployment requires approval for that exact
  candidate. The older `a87f3ba` approval referred to a rollout already
  completed and subsequently superseded.
- Owner-approved read-only VM audit is effective on both configured Proxmox
  sources. Nyx-4 verified complete guest enumeration without access-denied
  exclusions. This supports inventory and reported power state, not guest OS,
  application, or workload health. Production still misroutes a cluster-wide
  guest-status question; candidate `9511c75` fixes the route, includes source
  read timestamps, and limits completeness claims to configured source scope.
- The approved owner deployment has linked read-only inference catalogs and
  fixed-command GPU telemetry. Samples are timestamped and point-in-time; they
  do not measure CPU, attribute GPU use to a process, prove inference execution,
  or guarantee model fit. Nyx-4 applied the scoped persistence-service
  correction and verified affected inference services remained available
  without restarts; no reboot was performed, so reboot persistence remains
  unverified.
- Fresh authenticated dogfood completed: owner source-coverage question in
  4.7s, Household A everyday status in 4.1s, and Household B network-slowdown
  question in 4.1s. Household answers disclosed no private topology or
  owner-only infrastructure detail. A separate fresh owner query again
  misrouted cluster-wide guest status as a physical-host question (4.55s),
  confirming the open production defect fixed by candidate `9511c75`. Protected
  raw evidence remains mode-0600 outside this repository.
- No P0/P1 is currently evidenced. This does not mean the homelab is fully
  healthy or completely observable; remaining coverage limits are listed below.

## Current repository work

- Proxmox, NetBox, Kuma, and service-native records retain their canonical
  identities. HADES does not join them by display name or IP alone and has not
  written to canonical inventory sources.
- Read-only adapters compose configured Proxmox inventory/power state, NetBox
  intended inventory, Kuma availability, service-native checks, inference
  catalogs/residency, and explicitly approved GPU telemetry. Partial, stale,
  contradictory, or unlinked observations remain qualified in the read model.
- Owner paths cover broad status, guest state, node activity, service placement
  and health, backups, model inventory/capacity, recent source activity, and
  bounded diagnosis. They do not infer guest/application health from host
  reachability or model execution from a responding catalog endpoint.
- Synthetic contracts cover source identity/scope, timestamps, stale and
  partial reads, disagreements, household redaction, model inventory, GPU
  samples, and owner response shaping. The current runtime candidate also
  exercises the complete/partial Proxmox route through composed Hermes.
- Household responses are checked before owner-only source reads. The latest
  fresh A/B dogfood passed the tested prompts without topology or operational
  detail disclosure; this is representative evidence, not exhaustive proof of
  all possible prompts.

## Remaining evidence

- NetBox's application-service catalog and VM records are empty; some Proxmox
  and Kuma observations still lack verified cross-source identity. Intended
  placement and correlation must remain unknown. Any NetBox write is separately
  gated.
- The configured Proxmox audit scopes are complete for current guest
  enumeration, but do not inspect guest operating systems or prove in-guest
  service health. The natural-language cluster summary and source timestamps
  are fixed in candidate `9511c75`, pending its exact-candidate deployment
  approval.
- GPU telemetry does not provide CPU utilization, process attribution,
  successful inference execution, or guaranteed model fit. Nyx-4 applied a scoped persistence-service
  correction and verified affected inference services remained available; no
  real reboot-persistence test has been performed.
- Recent task history is not a complete change log. Host OS, driver, package,
  and in-guest service events are not represented by connected sources.
  Network loss, throughput, DNS timing, and long-term trends are not measured,
  so causal network diagnosis remains limited.
- Backup answers expose configured jobs and bounded task metadata only. Backup
  contents, independent off-site custody, and restoreability remain unverified.
- Provider catalogs, reported residency, endpoint health, and free VRAM do not
  prove that a model can complete an inference workload. Model fit remains
  uncertain without model, quantization, context, runtime overhead, and
  workload requirements.
- Public `main` remains green at `c83ddd6`; homelab implementation is on the
  pushed review branch and has not been integrated into `main`. Current
  authenticated dogfood covers representative prompts only. Protected
  acceptance evidence remains outside this public repository.

## Repository and deployment authority

Public source contains generic code, test fixtures, and deployment-neutral
contracts. The private infrastructure repository owns topology, host IDs,
addresses, access configuration, live deployment provenance, and private
acceptance records. The owner deployment uses an explicitly reviewed read-only
source configuration and an overlay candidate with a recorded rollback.
Synthetic evidence is not live infrastructure proof. Any further production
change requires a tested candidate, explicit scope, and rollback.

### Historical authenticated follow-up snapshot — 2026-10-03

- At this historical checkpoint, deployed code candidate `4a4bfdc` had passed
  Public CI run `37159647718`; `main` was `c83ddd6`. The candidate was not
  merged into `main`. Current deployment and review-branch state is recorded
  above.
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
- Gaps recorded at that historical checkpoint included selected-scope Proxmox
  visibility, an empty NetBox application-service catalog, incomplete network
  trends and backup verification, and unverified successful inference. Consult
  the current status and remaining-evidence sections above for their present
  disposition.

### Proxmox restore follow-up routing — 2026-10-03

A fresh owner follow-up asking whether recent backup restore checks left temporary
Proxmox guests present was routed to repository Backup Check status instead of
current guest inventory. The earlier cluster-wide guest question also exposed a
separate production route defect, already captured by the current review
candidate. Source code now adds an owner-only bounded route that joins recent
restore task guest IDs to current Proxmox inventory by stable source and guest
identity. It reports current presence/power state only when inventory scope is
complete, preserves unknown for partial scope, and states that task history and
guest health are bounded. A public-research privacy false positive on generic
infrastructure prompts was fixed while named-person current-location requests
remain refused.

Focused public-research, homelab service-health, deterministic decision API,
direct MCP routing, overlay composition, Python compilation, and Hermes runtime
contracts pass. The Hermes runtime test confirms the restore follow-up reads
recent Proxmox activity plus current inventory for an owner, does not fall back
to repository backup status, and performs no privileged reads for a household
user. These are repository/synthetic contract results; the new code has not
been deployed or owner-dogfooded. Production remains unchanged pending approval
of the exact new candidate.

### Deployment-composition gate — follow-up

The first implementation was placed only in the clean source conversation
handler, which the focused production overlay composer does not copy. Before
rollout, the restore-state path was moved into the composed homelab route and a
higher-priority owner/household preflight was added ahead of backup fallback.
The composer regression now asserts that ordering. A fresh read of the deployed
overlay was composed locally without changing the VM; the resulting artifact
passed the composed Hermes runtime check for owner source reads, household
redaction/no source reads, and source outage fail-closed behavior. The public
research policy test also confirms generic Proxmox/restore questions are not
classified as private-person requests while person-location controls remain.
The composed-route follow-up was committed as `e4b6084`; after the partial-feed
certainty correction, the current candidate is `544cd06` and Public CI passed
on run `37173378921`. The updated composed Hermes artifact passes against the
freshly read active production overlay. A final read-only VM check confirms the
service remains active/healthy and the overlay still matches that base.
Production remains unchanged. Any rollout request must identify the exact
resulting artifact and state its file scope.

### Partial restore-history result handling

A final response audit found that the no-match branch could say no recent
restore task was found even when a Proxmox task endpoint was partial, truncated,
unavailable, or had a malformed event list. The route now reports that recent
restore history cannot establish whether there are matching guests unless all
relevant task feeds are complete. A regression covers empty partial/truncated
history. Focused homelab, privacy, composer, clean Hermes runtime, and composed
runtime checks pass locally. This changes the composed artifact; hosted CI and
a new exact-candidate review are pending. Production remains unchanged.

### Fresh production owner/household baseline — 2026-10-03 CDT

A fresh-chat owner/Household A baseline on VM 802 reproduced both known owner
routing defects: the cluster guest-state question still receives a physical-host
answer, and the restore follow-up still reaches repository Backup Check status.
Both fresh Household A questions received generic infrastructure boundaries;
no private topology detail matched the protected acceptance filter. The owner
restore response is present in chat history; the initially false persistence
check was a Markdown-versus-rendered whitespace mismatch, and the formatting-
normalized response content matches. Stable-render response samples were
3.7–4.5 seconds. The websocket completion marker was absent, so earlier
90-second harness timings are invalid and not treated as application latency.
Raw responses remain in mode-0600 `/tmp` evidence, outside this repository.
Production remains on the previous overlay pending exact-candidate approval.

The fresh owner broad-status prompt returns a partial live view composed from
Proxmox, NetBox, Uptime Kuma, identity links, and inference providers. It says no
fresh configured Kuma probe is failing, distinguishes endpoint reachability
from application readiness, leaves 15 unlinked observations separate, and
qualifies provider catalog/residency as insufficient evidence of generation or
free GPU capacity. Fresh owner and Household A turns persisted; Household A
received only the generic boundary. The owner answer uses “current”/“fresh”
wording but does not print per-source retrieval timestamps, so useful source
provenance remains less inspectable than the underlying adapter evidence.
Protected raw responses remain outside the repository.
