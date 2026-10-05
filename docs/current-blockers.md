# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
private account identifiers, credentials, deployment identifiers, and raw
acceptance transcripts belong in protected operator records. These statements
summarize engineering evidence; they are not a live infrastructure probe.

## Current convergence checkpoint — 2026-10-05 07:45 UTC

Public `main` is `ae4cc444d323bd33e45c8bb73d40f4ff8e77e7a9`; exact Public CI
[37254848424](https://github.com/p0rkm4th/hades/actions/runs/37254848424) passed.
Aster integration branch `codex/aster-homelab-checkpoint-redacted-20261004` is
based on that main. Candidate `1684f78736d015dd6ea25fa869e4a90694993cf9`
passed exact Public CI [37277326937](https://github.com/p0rkm4th/hades/actions/runs/37277326937).
Code candidate `b8258e8724219cd34cb31c37b9d9165736b5440e` with status checkpoint `21165bf6ce3c7ecfc09e9749dd07eee683d60d00` passed exact Public CI
[37278311508](https://github.com/p0rkm4th/hades/actions/runs/37278311508). The installer
preflight verifies the complete homelab Python package against tracked source,
rejects links, and checks runtime traversal/readability. Aster independently reran
preflight, install-source-provenance, install-failure, reconstruction closure,
deployed provenance, syntax, current-tree safety, and introduced-history checks; all pass. The following source candidate `c5e865aca1f78a70598d50bae4a11b919039351c` moves pure guest-visibility rendering from `sitecustomize.py` into `homelab_views.py`; exact Public CI [37278760219](https://github.com/p0rkm4th/hades/actions/runs/37278760219) passed. NYX-036 package-drift doctor checks are integrated locally in `57d4c14e`, bind to the active Hermes working directory and environment-file profile, and pass focused tests. Combined hosted CI and the final active-unit false-PASS review remain pending; Nyx's c5 extraction review found no material issue. No source candidate is promoted or deployed.

The older `codex/gpu-telemetry-parity-20261004` reference is not a merge
candidate. Public CI [37222211701](https://github.com/p0rkm4th/hades/actions/runs/37222211701)
failed at `Check public history`; NYX-018 independently reviewed and accepted
Aster's semantic classification. No unique safe behavior merits porting. The
current guard reports one actual branch-only host-local path in historical
commit `ed1d5351` (the value is omitted here). Its final tree removes
Kuma `observed_at` and NetBox pagination-coverage semantics that current main
and focused tests preserve. No wholesale import is planned. Its duplicated
inference view code is less complete than main's freshness/provenance behavior,
and deleting the extracted view modules concentrates more code in the MCP
server. The old tip also removes `homelab_views.py` from installer, doctor,
validator, and manifest closure checks, weakening the reconstruction contract.

A fresh source/test comparison found two additional old-line regressions.
Its named service-health helper removes the owner-scope guard, and its route
calls that helper without passing scope; the old contract tests the household
boundary separately but does not exercise a household service-health call.
Current main passes scope and asserts the household helper path returns no
owner detail. A synthetic direct-helper call on the old tree can return an
injected monitor label, but every current callsite is owner-gated; this is a
latent defense-in-depth/test regression, not evidence of a household-reachable
or live disclosure. The old NetBox projection also drops
pagination completeness, while its service-placement fallback treats an
`OK` response with no rows and no explicit coverage as a confirmed empty
catalog. Current main retains `UNKNOWN` unless coverage is explicitly
complete/empty; its focused adapter tests pass complete, empty, partial, and
unknown cases. The old branch's focused tests omit several of main's
unavailable-Kuma and missing-service-identity cases.

Homelab main preserves Kuma `last_updated` as `observed_at`, independent of
freshness. A fresh 2026-10-05 read-only package comparison confirms the active
profile-selected adapter matches current public source except `reconcile.py`,
with no additional Python modules. Direct content comparison shows the
deployed `reconcile.py` matches the superseded GPU-parity tree, while its
`server.py` matches current `main`; this is the concrete source of the observed
fresh-without-`observed_at` mismatch. The active adapter read returned status
`OK` and 11 availability rows marked fresh, but none had `observed_at`; the
live timestamp contract therefore fails. The service catalog was empty, so
placement remains unknown. This direct adapter result is not owner-UI or
application-health acceptance. Preserve the active deployment-local overlay.

The candidate at `10dd2fd1` extracts the pure backup formatter; its focused
contract and hosted CI pass. Commit `d0c74306` adds a
provenance guard comparing the profile-selected generated homelab adapter's
complete Python module set and bytes with the clean tracked package. Commit
`7de443d7` adds a deterministic household denial for infrastructure inventory
and administrative-detail prompts. `f700e892` extracts provider-native,
read-only inference catalog parsing while retaining credential/TLS transport,
identity mapping, and composition in the server. The package-provenance
fixture now covers the added provider sibling. Focused contracts, public
safety, and hosted CI runs `37264553916`, `37264554854`, and `37265041968`
pass. Neither change is deployed. NYX-018 lineage and NYX-017 no-dispatch
reviews are accepted. The hostile-household runtime regression and corrected
partial-source contradiction assertion are committed in `2e62ffde` and exact
Public CI `37273578676` passed. NYX-026's stale review-status finding is corrected. NYX-028's Proxmox visibility extraction is accepted; the cherry-picked candidate passed exact Public CI `37274388982`, and public-tree/history checks pass. Docs refresh `7ba90aa7` passed exact CI `37274614406`. NYX-029 found helper failures abort before MCP/model dispatch without private leakage (P2 availability). NYX-030's loader/alias/renderer failure tests are committed in `1c4f280e` and the focused runtime contract passes locally and exact Public CI `37275149451` passed on head `71cf0497`. NYX-032 closed that P1: enabled required `homelab-readonly` registrations now require a path-backed `server.py` package identity; synthetic tests reject HTTP, `-m`, `-c`, and wrong-executor forms while preserving unrelated MCP transports. Aster independently reran provenance and reconstruction-closure tests; exact Public CI `37276510518` passed on candidate `32d6a6a9`. This source fix is not deployed. Earlier docs/status head `1d9dda555e56e76d33a371104e23d0e807e231dc` passed exact Public CI run `37275450730`. NYX-033 accepted the provider boundary but found an authenticated redirect P1. NYX-034 source candidate `1684f787` passed exact Public CI `37277326937`. NYX-035 installer closure is integrated as `b8258e87`; candidate and status checkpoint passed Public CI `37278311508`. NYX-036 doctor-time drift detection is integrated locally as `57d4c14e`; combined hosted CI and the final active-unit false-PASS review are pending. Main promotion and deployment remain pending. A live household
UI prompt exposed the intent-classification gap; no concrete host data was
returned, and fresh post-deployment UI verification remains open. Runtime
package parity and monitor observation-time output also remain open.

Prior targeted owner/household dogfood, synthetic failure contracts, and
backup metadata inspection remain bounded historical evidence. Full
application restore, independent-device/off-host custody, live outage and
contradiction acceptance, native service-health/placement coverage, network
trends, and normal-user outage acceptance remain open. The homelab campaign is
**PARTIAL**. Exact runtime hashes, private topology, rollback paths, and raw
acceptance transcripts remain in protected operator records.

**Next:** qualify the combined candidate including NYX-036, complete its adversarial review, then continue source/runtime reliability work. Main promotion and deployment remain open.
Prepare a coherent full-package deployment only after
review and promotion. Then deploy the
reviewed household boundary fix with hash-guarded rollback, recheck household
denial and safe status in the live UI, and verify coherent runtime package
parity plus `observed_at`. No runtime deployment has been made during this
checkpoint.

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
