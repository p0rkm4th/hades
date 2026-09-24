# Current blockers and owner gates

This is a concise, public-safe handoff list. It distinguishes work that needs
an owner decision or secret from defects that can be repaired independently.

## Requires owner or operator input

| Area | Current gate | What unblocks it |
|---|---|---|
| Production HADES homelab cutover | VM 802 (`hades-core`) is the canonical production Core. Owner identity, migrated application state, distributed model routing, rollback custody, and post-cutover client access are accepted; laptop production/runtime/model cleanup is complete with unknown and development material preserved. | Continue owner-visible capability expansion and close only the remaining optional/external gates. |
| Hermes 0.21.2 production promotion | Promoted on VM 802 with a rollback package verified on Alexandra. The live model smoke passes. The bounded candidate suite has one upstream SQLite repair-test failure under the VM's SQLite 3.46.1 build; the failure is isolated to forensic repair behavior and is not a live gateway/model-path failure. | Track the upstream SQLite repair-test issue; do not roll back the production runtime unless live gateway, identity, state, or model behavior regresses. |
| Web/search owner follow-up | Authenticated owner sign-in, live model catalog, real WebUI chat, fresh authenticated search, and live static-page evidence are accepted on VM 802. | Keep search snippets distinct from `PAGE` evidence; dynamic/interactive, login-required, and privileged browser workflows remain intentionally unavailable. |
| Recipe URL/paste owner acceptance | Authenticated owner preview → explicit confirmation → canonical Grocy read-back passed on VM 802 with synthetic data; cleanup returned canonical state to baseline. | Harden representative public/messy-page, duplicate/re-import, serving-resize, and shortage/add-missing composition; keep real owner data review-gated. |
| Shared Channels candidate promotion | Candidate isolation, restart persistence, live feature configuration, and preserved-owner private-channel create/post/read/delete acceptance pass on VM 802. | Keep Channels private/owner-scoped; do not transfer Hindsight or owner authority through membership. |
| Homelab read-only | Proxmox and NetBox least-privilege read-only inputs are provisioned; live owner dogfood reports Alexandra/Erebus, separates GPU inventory from runtime liveness, and invokes the bounded current-LAN scan without writes. NetBox contains seven physical/observed records and Kuma publishes 11 LAN-scoped monitors through the HADES read-only path; VM 802 is live but its NetBox intended-inventory record and two Kuma destination monitors remain plan-only pending the authoritative address reservation. Tartarus and Hypnos now pass native NVIDIA/CUDA smoke, SMART, network, time, capacity, and controlled reboot-persistence probes; both `eno1` profiles autoconnect on boot; Podman/NVIDIA CDI is configured, while GPU-container execution remains open. Hermes' controlled reboot did not restore ARP/SSH/management reachability and requires console/power recovery. Thanatos is reachable but its Secure Boot/`nouveau` state gates NVIDIA activation; its management workloads were preserved, and `/dev/sdd` has a historical SMART anomaly requiring follow-up. `.113` is now identified as an excluded Sony PS5, not a server. | Recover Hermes at console/power level, close the Rocky GPU-container gate, resolve Thanatos firmware/driver policy and `/dev/sdd` storage follow-up, locate the planned seventh server, finalize the VM 802 address reservation, apply the plan-only NetBox/Kuma updates through their operator surfaces, and complete hardware/network acceptance; scan evidence remains review-only. |
| Home Assistant read-only | No approved URL, token, entity allowlist, or exposure path is configured. | Approve the selected read-only entities and provide the scoped token/path. |
| Real finance | Natural-language statement inspection and write-free Actual previews are DOGFOOD GREEN; production finance mutation remains intentionally inactive. | Approve the Actual Budget environment/budget, historical imports, retention, secret storage, destination-account policy, and later live-sync provider. |
| Deterministic automation | No concrete n8n workflow, actor mapping, confirmation rule, or rollback contract is approved. | Approve one bounded workflow and its capability boundary. |
| Encrypted off-host recovery | Encryption key custody, off-host destination, retention, and plaintext-retirement policy are not selected. | Provide an operator-managed key and destination policy. |
| First real household user | Household Alpha is ready; onboarding needs the chosen real identity and credential flow. | Owner supplies or authorizes the intended identity/invitation. |

## Independent technical work status

- **Maintained:** Clean-machine reconstruction remains an available
  maintenance/recovery evidence lane; capability expansion is the active
  independent workstream. The public version manifest, host/filesystem contract,
  operator-input template, idempotent test-mode installer, non-mutating doctor,
  install validator, and rerunnable disposable rehearsal are present. Two
  independent pristine Fedora guests now pass the credential-free contract
  rehearsal and synthetic restore checks. Two independent fresh Fedora 44
  guests completed the real privileged installer path, reboot recovery,
  doctor, validation, and owner-style synthetic checks with generated private
  deployment records. The current-HEAD rerun now emits immutable records
  directly and passes the real preflight, deployment, reboot, and validation
  path. The disposable full application reconstruction and synthetic household
  soak now pass; the independent fresh Rocky generated-installer path and
  Alpha/Beta restart/isolation soak and generated-runtime reboot recovery now
  pass, while full owner-visible composition and any newly selected model or
  provider lanes remain separate acceptance work.
- **Added:** The reconstruction contract now injects an interruption after
  preparation and verifies that a rerun preserves prepared state. Invalid
  private Compose, mutable image pins, and unsafe secret permissions fail
  before target mutation; bounded upgrade and preservation-first decommission
  rules are canonicalized in `docs/upgrade-decommission.md`.
- **Added:** `scripts/proxmox-bootstrap.sh` provides a plan-first, explicit
  Proxmox-to-supported-guest handoff. Its API apply path remains unexercised
  because no approved Proxmox endpoint or credential is configured.
- **Added:** The credential-free backup→destroy→restore drill preserves stable
  Alpha/Beta subject IDs, memory-bank mappings, conversation marker, and Grocy
  stock. It does not substitute for private encrypted off-host recovery.

- **Complete:** The credential-free Qwen multi-user long-context lane is
  complete: the
  repeatable Alpha/Beta/Gamma harness passes 24/24 bounded turns, including
  corrections, topic switches, abandoned mutations, pronouns, and recall.
  Routing context now excludes tool-role payloads so stale observations cannot
  steer later capability selection; the current user/assistant conversation
  text remains bounded and current-turn preserving.
  Authenticated HADES-session acceptance remains an owner-authenticated
  end-to-end gate, not an unrecorded independent defect.
- **Complete:** The pinned Open WebUI private-chat soak creates Alpha and
  Beta through the real application routes, persists Alpha's synthetic model
  response, denies Beta access to Alpha's chat, and preserves the chat across
  restart. The model backend and state are disposable; this does not claim
  Hermes/Hindsight/Grocy end-to-end behavior.
- **Complete:** A fresh synthetic web and recipe capture records model, tool,
  continuation, and total timings. Both workflows are below the repeated
  roughly-30-second optimization threshold; model/continuation is the bounded
  future target and no adapter rewrite is justified.
- **Covered:** Isolated Grocy authoring edge cases and canonical reconciliation
  are covered;
  pre-write connection failures return `FAILED`, while ambiguous outcomes
  remain `OUTCOME UNKNOWN` and are never blindly replayed. Reopen only for a
  newly demonstrated mutation defect.
- **Added:** Receipt OCR now has a credential-free end-to-end review dogfood
  contract from upstream-shaped evidence through exact Grocy matching,
  explicit quantity/confirmation gating, canonical synthetic intake,
  duplicate reconciliation, and low-confidence rejection. The owner-scoped
  WebUI now supports an explicit reviewed apply with canonical Grocy read-back;
  representative messy-receipt accuracy and broader household/browser
  acceptance remain staged work.
- **Added:** Homelab control planning now has a write-free Proxmox contract
  for exact guest targets, canonical preconditions, owner authorization,
  confirmation, and read-back outcome reconciliation. It deliberately has no
  executor; real homelab credentials and scope remain the only gate to a
  private execution adapter.
- **Added:** Bounded Nmap evidence now has a transient review projection for
  observed IPs, hostnames, open ports, and exact NetBox context matches. It is
  explicitly non-authoritative and performs no inventory writes.
- **Added:** Local push-to-talk voice now has synthetic household dogfood for
  pantry, web, preference, attempted-mutation, uncertain-speech, and STT
  outage turns. The bridge normalizes provider exceptions to `FAILED`; voice
  remains non-authenticating and non-authorizing.
- **Hardened:** The bounded Agent Zero bridge now rejects credential,
  infrastructure-control, shell/SSH/Docker, and write-capable task text before
  upstream delegation. Harmless bounded inspection remains available; the
  interactive operator surface and real broader tasks remain separately
  staged/owner-scoped.
- **Expanded:** Recipe ingestion now converges URL, pasted text, pasted HTML,
  and pasted JSON-LD on one bounded normalized preview path. Grocy writes still
  require exact product resolution, review, confirmation, and canonical
  read-back; fetched pages with clear visible recipe sections now use a
  review-required fallback, while site-specific/browser extraction and owner
  acceptance remain staged.
- **Hardened:** The staged recipe MCP now validates its Grocy API-key input as
  a bounded regular non-symlink file with safe permissions before any request.
  The secret-boundary regression passes; no production recipe MCP is enabled.
- **Hardened:** Browser profile selection now requires a strict boolean owner
  authorization value; malformed truthy values cannot select the privileged
  profile. Anonymous browsing and explicit-submit fixture acceptance remain
  green.
- **Added:** An HADES `browser-research` proxy now registers only the pinned
  anonymous navigation/read surface and requires an explicit public-host
  allowlist. The raw Playwright MCP surface remains unregistered; draft,
  submit, storage, file, evaluation, and privileged-profile operations are
  still an expansion item, not an owner gate.
- **Hardened:** The Actual read-only wrapper now rejects unsafe password files
  and missing explicit budget selection; it cannot silently choose the first
  budget. Finance remains production-gated and read-only.
- **Added:** Local finance files now have a Hermes-registered, inline-base64
  preview MCP. CSV mapping, duplicate analysis, explicit Actual account
  targeting, owner-only synthetic dogfood, and timeout-after-write
  reconciliation pass; the unregistered native-writer contract now also
  preflights duplicates and classifies canonical read-back as `SUCCEEDED`,
  `FAILED`, or `OUTCOME UNKNOWN` without blind replay. Native Actual execution
  remains authorization-gated.
- **Hardened:** Home Assistant security filtering now rejects garage/door/alarm
  controls even when represented as `switch`, `button`, or `input_boolean`,
  while retaining ordinary read-only entities.
- **Closed:** Hermes 0.21.2 is the live production runtime. Session-stream,
  OpenAI-compatible SSE, and liveness paths now request hard cancellation and
  emit privacy-safe turn lifecycle telemetry. Local and deployed focused
  suites pass (`98 passed` remotely); direct authenticated SSE disconnect
  telemetry records cancellation and lease cleanup in milliseconds. The
  pinned Open WebUI artifact was additionally rebuilt with an explicit
  downstream-disconnect watcher (`hades-open-webui:0.11.1-hades-cancel-repair`)
  and is live on VM 802. Its authenticated browser SSE abort returns
  `AbortError` after receiving stream data. Provider workers may still ignore
  cancellation internally, but they no longer retain HADES leases or policy
  authority. Remaining physical voice acceptance and provider throughput
  qualification are separate gates. Evidence is recorded in
  `hades-infra/acceptance/hermes-client-disconnect-p1-closure-20260921.md`.
- **Improved:** The post-P1 CURRENT follow-up expanded the sanitized Decision
  Plane corpus from 31 to 50 cases and added bounded context composition,
  referent clarification, and composite multi-domain recommendations. The
  expanded replay is 100% on its labeled intent, capability, tool-family,
  clarification, and reasoning slices at ~0.073 ms p95; production steering
  and candidate shadowing remain disabled.
- **Added:** A public configuration-drift guard now checks the tracked compose
  set and reconstruction-manifest coverage.
- **Found and contained:** The current public tree now passes private-topology
  safety after redacting destination evidence and deriving workstation paths.
  Reachable pre-redaction commits still contain historical private values; no
  history rewrite is performed without explicit release/owner authorization.
- **Activated:** Current connected-LAN discovery is authorized and has been
  exercised through the HADES-owned bounded MCP worker. It resolved the
  primary directly connected `/24`, found live hosts, produced transient
  review candidates, and performed zero inventory writes. Dedicated Proxmox
  PVEAuditor token inputs now return live Alexandra/Erebus node state through
  the owner-scoped HADES path. NetBox read-only inventory credentials are
  provisioned and its seven observed host records are seeded. Uptime Kuma now
  has 11 LAN-scoped monitors and a published `hades-infrastructure` status
  page consumed by HADES without admin credentials; Tartarus and Hypnos have
  since recovered SSH reachability and both `eno1` profiles now autoconnect on
  boot, while staged GPU runtime acceptance remains open.
- **Updated:** The actual-image full-application composition passes at the
  current checkpoint and on independent fresh Rocky 10.2 guest VM 802,
  including restart persistence and Alpha/Beta isolation. The fresh guest
  installed Docker CE/Compose through the repaired Rocky host-preparation path
  and all seven pinned containers reached health. The installer-generated
  Hermes gateway/application-record path and Alpha/Beta restart/isolation soak
now pass; full owner-visible composition and any newly selected model or
provider lanes remain open rather than being implied by the synthetic soak.

Completed independent evidence now includes the synthetic homelab and Home
Assistant read-only fixtures, mixed-domain memory/web/operator composition
contract, cross-domain conversation dogfood, source-of-truth contradiction
harness, reconstruction manifest and drift guard, static security audit,
transient-error memory hygiene, Hermes qualification classification, stable-v1
readiness-map validation, and long-context current-turn preservation
regressions.
The synthetic fresh-install household-soak contract now composes the generated
private-input install path with the owner-style boundary suite, including
receipt intake, finance-file handoff, homelab control planning, and local voice
dogfood; the independent fresh Rocky generated-install path and Alpha/Beta
restart/isolation soak and generated-runtime reboot recovery now pass, while
full owner-visible composition and any newly selected model/provider lanes
remain open.
The fresh owner-UI web follow-up, recipe browser sequence, real integrations,
and recovery custody remain owner/operator gates rather than hidden defects.

The coordinated revocation bridge is accepted: it deletes the Open WebUI
account before the directory identity and verifies that the prior bearer token
is rejected. Automatic directory-event synchronization remains a documented
future architecture choice, not an actionable defect in the current ordered
procedure.

## Explicitly not blockers

- Household Alpha readiness is complete.
- Production Hermes is healthy on the promoted 0.21.2 runtime; the preserved 0.14.0 service/artifact remains the rollback source.
- Finance is not missing implementation; it is deliberately authorization-gated.
- No production Hermes, finance, homelab, or Home Assistant mutation is
  authorized without the corresponding approval; the homelab production
  cutover itself remains pending owner acceptance and authoritative DNS.
