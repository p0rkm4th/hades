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

- Review branch documentation baseline `608598c` passed Public CI run
  `37176967000`; public `main` remains green at `c83ddd6`. The homelab source
  implementation `e7fb6a1` passed Public CI run `37175267641` and is now
  deployed to the owner VM. Private artifact hashes, root-only rollback, and
  live acceptance captures are recorded in `hades-infra`.
- Fresh owner acceptance after deployment now includes per-source read times in
  broad status; complete-scope Proxmox guest state with separate running and
  stopped groups; and restore-task follow-up joined to current guest inventory,
  bounded to the recent task window. Household A/B received generic boundaries
  for those same infrastructure questions. Persisted chats show no household
  tool-role messages or tool-call records. Power state is still not represented
  as guest OS, application, or workload health.
- Owner-approved read-only VM audit is effective on both configured Proxmox
  sources. Nyx-4 verified complete guest enumeration without access-denied
  exclusions. This supports inventory and reported power state, not guest OS,
  application, or workload health. Fresh production owner dogfood still
  confirms broad status is partial and omits per-source timestamps; the
  candidate fixes this response as well as the cluster-wide guest-status route.
- The approved owner deployment has linked read-only inference catalogs and
  fixed-command GPU telemetry. Samples are timestamped and point-in-time; they
  do not measure CPU, attribute GPU use to a process, prove inference execution,
  or guarantee model fit. Nyx-4 applied the scoped persistence-service
  correction and verified affected inference services remained available
  without restarts; no reboot was performed, so reboot persistence remains
  unverified.
- Fresh authenticated owner dogfood returned eight timestamped GPU samples
  across three inference endpoints and refused to guarantee model fit. Nyx-4
  refreshed the deployed read-only capability input from the current private
  inventory with a protected rollback; a fresh owner answer now uses the current
  dated capability inventory, avoids stale/historical qualification, and
  preserves uncertainty about model fit. Raw evidence and private hashes remain
  outside this repository.
- No P0/P1 product regression is established by these samples. Canonical-source
  gaps and incomplete operational coverage remain open evidence, not an
  all-clear.

## Current repository work

Older dated progress entries below preserve their state at the time; the
current deployment and evidence above supersede earlier statements that the
combined owner routes were still pending.

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

- NetBox's application-service catalog and VM records were empty at the latest
  source audit; some Proxmox and Kuma observations still lack verified
  cross-source identity. Intended placement and correlation must remain unknown
  until canonical records are reconciled and live reads confirm them. Nyx-4 is
  assigned a bounded, evidence-backed NetBox/Kuma reconciliation; HADES itself
  remains read-only and receives no writer credentials.
- The configured Proxmox audit scopes are complete for current guest
  enumeration, but do not inspect guest operating systems or prove in-guest
  service health. The natural-language cluster summary, restore follow-up, and
  broad source timestamps are deployed and passed fresh owner plus Household
  A/B acceptance.
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

The deployed capability-matrix refresh and fresh owner acceptance supersede
the earlier stale-input finding above. Network-wide host/package/image currency
and natural backup-timer evidence remain in progress in the private operations
handoff; do not infer fleet currency from the source inventory.

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

### Broad-status source freshness follow-up — 2026-10-04

The exact composed candidate adds up to six source retrieval timestamps to owner
broad summaries and carries the previously tested owner routes for cluster-wide
Proxmox guest status and restore-check guest presence. Household wording/source
access remain unchanged. A follow-up found composer output could vary with
Python hash seed because helper definitions were emitted from a set. The
composer now sorts emitted functions and global assignments; a regression
composes under two hash seeds and compares exact bytes. Two builds from the same
base now produce identical output. Deterministic overlay SHA-256 is
`214c755eeaf414d26a1be6d8609c8dd4d1760215ea2b3489763eecda5ac128e8`, based on
last verified active SHA `d697717418e00da5693940ea9351de4faaf1affc35dedaea9ac7f49ee29277a2`.
The candidate's composed runtime covers all three owner routes and household
boundaries. HADES `e7fb6a1f9f712688d2fd5437acf8443b89b6b21a` passed Public CI
run `37175267641`. Exact-scope deployment approval and fresh owner/Household A/B
acceptance remain pending; the live active base must be rechecked before
installation. Previous approval requests named nondeterministic artifact
hashes and must not be used.

Fresh owner/Household A production dogfood reconfirmed the current behavior.
The owner broad answer remains partial, omits source retrieval timestamps,
keeps 15 cross-source identity observations unlinked, and explicitly separates
probe reachability from application readiness. Household A received a generic
computer-status boundary and an honest "no current check" answer for the game
server. Four-prompt protected raw evidence is mode 0600 at
`/tmp/aster6-homelab-summary-ui-20261003.json`; it is not committed. No runtime
configuration was changed. Nyx-4 has a read-only assignment to verify whether
the empty NetBox application-service catalog is expected or a missing canonical
record; no NetBox/Kuma mutation was requested.

Fresh owner GPU dogfood returned eight timestamped device readings across three
configured inference endpoints (roughly 0.4–7.9 GiB free per device, zero
utilization at the sample). The answer treated these as point-in-time values,
said model fit remained unknown, and disclosed stale hardware role/capability
inventory. Household A received only generic inference-check availability and
was told generation was not tested; its game-server health remained unknown
because no current check was available. Protected evidence is mode 0600 outside
the repository. Nyx-4's private coordination request now includes checking the
capability freshness and current Kuma monitor records; no source writes have
been made. A new owner follow-up to the broad summary returned retrieval times
for readable sources, labeled missing source timestamps, and clarified that a
read-completion timestamp does not make an older observation live. Household
A's matching freshness follow-up stayed at the generic boundary without
privileged source reads. This validates the existing on-demand provenance path
while the pending combined overlay makes those times visible in the initial
owner summary.

The latest fresh before-rollout production chats still reproduce the two owner
routing defects on the active base: cluster-wide guest state is treated as a
physical-host query, and restore-check guest presence falls back to HADES
repository Backup Check status. Household A and B receive only the generic
boundary for both questions, without host or guest details. The deterministic
overlay candidate contains the tested owner routes; protected raw evidence
remains mode 0600 outside the repository.
