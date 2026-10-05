# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
private account identifiers, credentials, deployment identifiers, and raw
acceptance transcripts belong in protected operator records. These statements
summarize engineering evidence; they are not a live infrastructure probe.

## Current convergence checkpoint — 2026-10-05 UTC

### Published-history privacy audit

A full reachable-history scan of current public `main` (`8b995715`, 870
commits) found 1,509 historical matches for two apparently owner-specific
`.local` names across deployment/configuration, documentation, source, and
other files. The exact names are intentionally omitted here. Another 90
private-address matches across 86 commits are confined to synthetic
test/fixture locations. Host-local paths, tailnet names, MAC addresses, and
credential-like artifact paths were not found by these detectors. This does
not prove that inline API credentials or key material are absent; that content
was not inspected by the history audit.

The current source tree passes its sanitization scan, but the historical names
remain in already-published commits. Public history is not being rewritten;
the disclosure therefore remains an unresolved privacy limitation. Do not
describe all reachable HADES history as sanitized.

Homelab package code revision `2594e33b` is on `main`; docs/runbook checkpoint `85c1365a` passed candidate/main CI; main includes the deterministic composer for the tracked homelab package and its Public CI contract; candidate Public CI [37359442217](https://github.com/p0rkm4th/hades/actions/runs/37359442217) passed; post-promotion main CI [37359854855](https://github.com/p0rkm4th/hades/actions/runs/37359854855) passed; the runbook/checkpoint update passed candidate CI [37360970057](https://github.com/p0rkm4th/hades/actions/runs/37360970057) and latest main CI [37361152596](https://github.com/p0rkm4th/hades/actions/runs/37361152596). The composer produced the actual 13-module package from a clean source revision, and the current provenance validator accepted it. This is package-generation evidence only. The prior named-host workload renderer candidate/main CI [37355109128](https://github.com/p0rkm4th/hades/actions/runs/37355109128) / [37355337581](https://github.com/p0rkm4th/hades/actions/runs/37355337581) and latest docs checkpoint [37355836915](https://github.com/p0rkm4th/hades/actions/runs/37355836915) / [37356083937](https://github.com/p0rkm4th/hades/actions/runs/37356083937) passed. Main includes the deterministic package composer, CI contract, and documented profile-only rollout/rollback procedure. The old `codex/gpu-telemetry-parity-20261004` ref was `345cb1b6de5f9f51ad98986c88ab9f0693461921`; its latest CI [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701) failed public-history safety, and the introduced-history audit has one redacted local-path/private-address finding. NYX-001 and Aster found no unique public-safe behavior to port; main has stronger freshness/completeness contracts and separated view modules. Disposition is **UNSAFE / OBSOLETE REFERENCE**; its remote ref has been deleted and its clean local worktree is retained as evidence. No history was rewritten.

Current deployed Hermes-overlay and homelab-adapter hashes are **NOT VERIFIED** in this epoch. A fresh read-only package inventory disproves exact disk-tree parity for the active homelab MCP: 10 source files are present versus 13 in current main, two files differ, three expected modules are absent, and an extra cache directory causes the exact-tree validator to reject it. The active child command resolves to this package path; this does not prove which bytes are already loaded in memory. Main includes the tested package composer and a documented, not-yet-exercised profile-only switch/rollback; the full installer is unsuitable because it also replaces overlay/assets. Do not infer runtime parity from green source CI. Current main retains the `d8013f94` guard that denies household and missing-subject named-host workload questions before reading `homelab_summary`; focused tests assert zero source reads. The pure named-host renderer was subsequently extracted at `e93f497e`, with direct/module-wrapper parity and non-invocation assertions for unknown/unavailable routes.

Current main includes extracted Proxmox host-load/guest views and Kuma normalization, malformed Proxmox/NetBox container/row rejection, Proxmox enum validation, partial backup-node discovery, and a household guard for named-host resource questions and context-only resource follow-ups. The latter reads only the latest user-authored turn when resolving a pronoun follow-up; assistant history does not identify a host. Generic conceptual prompts remain unblocked. NYX-008–013 and NYX-015–018 reviewed source completeness and household privacy; candidate tests prove zero model calls, no homelab dispatch, and no sentinel leakage for protected household requests.

Homelab remains **PARTIAL** for owner-facing live use. Current-main runtime byte parity and fresh authenticated owner/household acceptance remain unverified. The narrow seven-chat result is on an older adapter revision and is historical evidence only. No production deployment or source ACL change occurred. No old-branch history was imported; NYX-001 semantic classification is complete and the unsafe/obsolete remote ref has been deleted, with the local evidence worktree retained. NYX-007 response-boundary tests and NYX-008 pure view extraction are on green main.

No independent encrypted off-host recovery destination or recipient is configured. The owner confirms no off-site backup is available now and considers this acceptable; no recovery artifact was created. Record this as a known recovery limitation, separate from the homelab read-source campaign.

Last protected read-only production provenance is dated 2026-10-05 and remains
the source for the historical composition statements below. Aster
re-verified from this session, using the documented strict SSH key, that the
HADES Core host identity matched, `hades-hermes` was active, Open WebUI
reported a healthy container state, and its direct health endpoint returned
HTTP 200. The configured owner-local DNS lookup timed out; related candidate
names were unresolved or timed out. These checks establish reachability and service
health only, not the selected adapter revision, functional chat behavior, or
owner/household acceptance. No host changes were made. A mode-0600
acceptance report records seven authenticated chats on the previously deployed adapter revision
`6bc6063702f73665a9cf666ca14cf7057d5924e`: four owner questions and three
household questions, zero turn errors, and no topology-leak flags on the
household answers. This is a narrow historical-package pass, not current-main
package parity or broad acceptance. Separate scripted owner/household
sign-in inputs returned HTTP 400; no password alternatives or resets were
tried. No current production deployment or infrastructure/source-ACL mutation
occurred in this epoch.

Reliability changes for malformed Proxmox backup rows, missing job IDs,
malformed task identities under guest exclusions, and an exactly-full
20-task response are on `main` at
`b315391b75e87a4ec382148092fdd740b36ba79f`. Candidate Public CI run
[37332438582](https://github.com/p0rkm4th/hades/actions/runs/37332438582) and
post-promotion run
[37332678905](https://github.com/p0rkm4th/hades/actions/runs/37332678905)
passed. Focused contracts and current-tree safety checks pass. The code remains
undeployed; live-source, runtime-parity, and authenticated owner/household
evidence remain unchanged.

A separate runtime follow-up candidate adds end-to-end owner-boundary coverage
for household and unverified-session Proxmox backup questions. The focused
Hermes runtime contract passes with no model or homelab-tool call and no private
details in either response. The fix is on `main` at
`0e468fff97567d4f85e4e50d76d2d039d58403ec`; candidate CI run
[37334351339](https://github.com/p0rkm4th/hades/actions/runs/37334351339) and
post-promotion run
[37334505737](https://github.com/p0rkm4th/hades/actions/runs/37334505737)
passed. It remains undeployed.

A fresh strict-key read-only production check found Hermes active and its
service working checkout dirty with local adapter/overlay edits. The selected
`hades` profile points its homelab MCP at one of several versioned generated
adapter bundles; that adapter differs from current `main` and does not include
the newly promoted backup-view route. Another profile configuration points at a
different release path and is not evidence of the running profile. The prior
claim that the active generated root lacked the adapter package was inaccurate:
the protected package exists but is inaccessible to the unprivileged SSH
account. No deployed files or host configuration changed. Runtime parity and
feature parity remain unproven; a reviewed package-complete composition is
required before deployment or runtime acceptance. The selected bundle's
`server.py` matches a tracked historical HADES source revision, while its
`server.py` and `reconcile.py` differ from current `main`; the current
`activity_view.py` and `backup_view.py` modules are absent from that bundle.
Other files match current tracked sources, so this is a mixed-version package,
not one reproducible Git revision. The deployed-provenance writer now has a
homelab-specific opt-in mode that checks an external adapter's exact file set
and contents against the clean tracked HADES package tree. Generic external
path-backed MCP sources remain rejected, and the canonical homelab registration
cannot use HTTP transport to bypass source identity. The current mixed-version
live bundle fails this exact-tree check. Its resulting identity attests
configured disk bytes at capture time, not what a process has already loaded
in memory.

A fresh direct call through the active read-only MCP returned overall `OK`,
Proxmox guest visibility `COMPLETE / ALL_GUESTS`, and eleven Kuma monitor rows
`UP`. The NetBox application-service catalog was healthy but empty, so current
service placement remains unverified. This is live source composition, not
owner/household chat acceptance or current-main package parity.

Private-infra recovery remains owner-managed: the checkout is dirty, no
independent encrypted off-host target has been specified, and the owner confirms
no off-site backup. Same-disk copies are not independent recovery.

**Next:** continue read-only source readiness and freshness checks using the
documented access contract. Keep the homelab read layer **PARTIAL** until
current-source composition, representative owner/household dogfood, and
runtime provenance are verified. Do not deploy this read-only view refactor
without a reproducible current-main composition and fresh behavior acceptance.

## Historical release baseline and prior evidence

Code checkpoint `f55bd0a` passed Public CI run `37240583967`. Earlier
source checkpoint `07b0055` adds NetBox pagination completeness and
contradictory-coverage handling. HADES calls the service catalog
complete or empty only when `count`, `next`, and `results` agree; missing pages
and malformed or contradictory metadata remain partial or unknown. Focused
synthetic source and response contracts pass.

A first private overlay composition accidentally removed adjacent helpers. The
hash-guarded rollback restored the prior overlay and adapter, and a fresh owner
chat confirmed recovery. The corrected composition changes only the intended
coverage and placement functions; the bundle's AST/fallback tests and Nyx-4's
independent read-only review passed. The revised adapter and overlay are now
active with Hermes and WebUI healthy. Fresh owner UI acceptance reported the
empty service catalog with probe-health caveats, refused to infer Minecraft
placement, and retained the bounded Agent Zero endpoint response. Household A
was denied internal host/address details with no topology leak. No source
permissions or infrastructure settings changed.

This closes the NetBox completeness slice, not the broader homelab campaign.
The deployed read layer still needs representative stale/partial live-source
checks, service-native application health, source-conflict dogfood, network
measurements, backup/recovery evidence, and broader normal-user dogfood.

Fresh owner dogfood found a status/freshness conflation for the hardware
capability matrix and a duplicated GPU count in aggregate inventory labels.
Source read status and data freshness are now separate; the matrix timestamp is
evaluated against a seven-day window, and aggregate strings such as `4x Quadro
P4000` are preserved without a second inferred count. The owner response keeps
provider-residency and host-health limitations while distinguishing recorded
inventory from timestamped GPU samples. Public CI run `37238630968` passed at
`86ca48f`; fresh owner and household UI checks passed, including household
redaction and unknown game-server status. These specific defects are closed.
The wider homelab reliability campaign remains **PARTIAL** pending live-source
failure/conflict checks, service-native health and placement coverage, network
measurements, and backup/recovery evidence.

The owner question “Is everything okay with the homelab?” now returns a
bounded status summary instead of a guest inventory dump. It distinguishes
fresh configured checks from guest power state and keeps incomplete service
placement, unmonitored application health, and backup-content/restoreability
unknown. Follow-up dogfood correctly identifies duplicate display labels as
separate stable identities rather than a source disagreement; an initial
candidate that misclassified these labels was rolled back before the corrected
candidate passed owner and household checks. Public CI passed at `f55bd0a`
(run `37240583967`). The broader homelab campaign remains **PARTIAL**. The
summary does not query backup schedule/task status, and network measurement,
service-native checks, stale-source acceptance, and synthetic restore evidence
remain open.

A separate fresh owner backup query returns bounded configured Proxmox
job/task evidence and repository-check status, but does not establish expected
guest coverage, backup contents, off-site custody, or restoreability. It
preserves unknown guest attribution, and a fresh household check withholds
private backup details. Backup recovery remains open.

Fresh owner/household network-slow dogfood returns configured-probe timing
samples only and explicitly declines a network-wide diagnosis. Packet loss,
throughput, DNS timing, and historical comparison are not currently available,
so network bottleneck and trend claims remain unverified. Household wording
withholds private infrastructure details.

Previously published history is preserved and still contains older private
identifiers. Current-tree sanitization and the introduced-range path/address
audit do not erase or certify every older public commit. The current branch tip
removes the destination-specific acceptance records and per-user share mapping,
uses explicit operator hostname input, and uses synthetic guest identities.

## Homelab read reliability — PARTIAL

HADES composes configured Proxmox, NetBox, Uptime Kuma, service-native, and
inference observations without creating a second inventory authority. Owner
reads distinguish freshness, conflicts, and unknowns. Current evidence does not
establish every intended node, service, GPU, backup, or network condition.
Host utilization is available only for observed Proxmox node rows; network
trends, general host operating-system state, in-guest service health,
filesystem capacity, and backup restoreability remain unknown unless a current
source explicitly provides them. Household status remains unknown when no
approved household-safe live check is configured.

A synthetic NetBox outage test seeds a stable Proxmox-to-NetBox link before
withdrawing NetBox. The adapter retains current Proxmox runtime and removes the
prior inventory identity, while a stale Kuma observation remains stale. A
separate authenticated UI test found and fixed local read-only adapter fallback
registration for deterministic owner routes; the post-fix UI acceptance
passed. The current deployed owner UI also distinguishes guest power/placement
from application health and reports provider read times; household leak checks
passed.

Remaining work:

- exercise stale-source and partial-source-outage behavior against live and
  synthetic feeds without promoting cached data to live truth;
- verify contradictory Proxmox/NetBox/Kuma observations remain visible;
- reconcile stable identity links and service placements;
- qualify backup coverage separately from local copies, contents, and restore
  success;
- complete reboot and synthetic restore acceptance;
- continue owner and household dogfood for service placement, failures, model
  inventory, and distributed placement;
- retain read-only enforcement and household redaction under partial outages.

Do not infer current state from a capability matrix, prior chat, memory, or an
old report. No infrastructure mutation authority is included.

## Separate owner or external gates

- Production cutover, client/DNS changes, or retirement of an existing runtime
  require their own explicit owner decision.
- Real household onboarding requires the selected identity and credential
  flow.
- Real finance, Home Assistant, off-host encrypted recovery custody, and
  privileged browser workflows remain separately gated.
- Infrastructure changes discovered during read-only inspection are assigned
  to the authorized infrastructure operator; HADES integration work must not
  modify hosts, networks, drivers, or hypervisor state.

## Evidence location

Detailed private acceptance records and the canonical machine matrix belong in
protected `hades-infra`. Public fixtures and contracts use synthetic names,
addresses, credentials, and measurements.
