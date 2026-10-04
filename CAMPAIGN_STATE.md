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
  or guarantee model fit. Reboot persistence remains unverified.
- Fresh authenticated dogfood completed: owner source-coverage question in
  4.7s, Household A everyday status in 4.1s, and Household B network-slowdown
  question in 4.1s. Household answers disclosed no private topology or
  owner-only infrastructure detail. Protected raw evidence remains mode-0600
  outside this repository.
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
  successful inference execution, or guaranteed model fit. Nyx-4 has a scoped
  request to correct a persistence-service issue; no real reboot-persistence
  test has been performed.
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
