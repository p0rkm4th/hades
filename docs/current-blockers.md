# Current blockers and owner gates

This is a concise, public-safe handoff list. It distinguishes work that needs
an owner decision or secret from defects that can be repaired independently.
The operational statements below retain their own evidence dates; this file is
not a live production probe.

## Release convergence update (2026-10-01)

Qualified release SHA `e7f4fa83e1970257ea522109828b4193827df28e` was promoted to `main` by fast-forward from `a654675d5e7d3e9109e442094a169260b6027fa7`. Hosted branch run [36896358861](https://github.com/p0rkm4th/hades/actions/runs/36896358861) and main run [36896801928](https://github.com/p0rkm4th/hades/actions/runs/36896801928) each completed 110/110 reported steps with zero failures or skips. The 104 local Public CI `run` steps also passed. Confirmation isolation, exact provisioning-plan binding, and authenticated synthetic cross-worker UI acceptance passed. No production change or owner acceptance is implied.

The promoted tree passes the current-tree guard and the introduced release range passes the history audit. The old base had one current-tip private path/address match and 90 in reachable history; the tip match was removed by promotion, while 90 already-published historical matches remain. Current-tree and introduced-release Gitleaks scans are clean. Public history was not rewritten. The next engineering action is a focused, low-risk `sitecustomize.py` extraction; owner/runtime gates below remain separate.

## Requires owner or operator input

| Area | Current gate | What unblocks it |
|---|---|---|
| Production HADES homelab cutover | VM 802 (`hades-core`) is the canonical production Core. Owner identity, migrated application state, distributed model routing, rollback custody, and post-cutover client access are accepted; laptop production/runtime/model cleanup is complete with unknown and development material preserved. | Continue owner-visible capability expansion and close only the remaining optional/external gates. |
| Hermes 0.21.2 production promotion | Promoted on VM 802 with a rollback package verified on Alexandra. The live model smoke passes. The bounded candidate suite has one upstream SQLite repair-test failure under the VM's SQLite 3.46.1 build; the failure is isolated to forensic repair behavior and is not a live gateway/model-path failure. | Track the upstream SQLite repair-test issue; do not roll back the production runtime unless live gateway, identity, state, or model behavior regresses. |
| Web/search owner follow-up | Authenticated owner sign-in, live model catalog, real WebUI chat, fresh authenticated search, and live static-page evidence are accepted on VM 802. | Keep search snippets distinct from `PAGE` evidence; dynamic/interactive, login-required, and privileged browser workflows remain intentionally unavailable. |
| Recipe URL/paste owner acceptance | Authenticated owner preview → explicit confirmation → canonical Grocy read-back passed on VM 802 with synthetic data; cleanup returned canonical state to baseline. Disposable authenticated Beta UI reads canonical feasibility and supports natural add wording for one exact saved recipe, canonical shortage-only list changes, canonical read-back, and safe retries. Recipe quantities now aggregate per product and convert through Grocy's product-scoped resolved factors from recipe units to stock units and then purchase units. The source now filters publisher/head/script/style/navigation/hidden text from the visible-text fallback; a malformed-JSON-LD messy-page fixture still extracts the article as a review-required preview. Same-source re-import now fingerprints normalized content: unchanged retries are distinguished from changed source content, and changed/legacy duplicates remain blocked from apply for canonical review. King Arthur, Simply Recipes, and Allrecipes public URL probes were previously accepted. Disposable authenticated household UI verifies known past-best-before stock is excluded from recipe feasibility; low-spend meal questions recommend only recipes covered by usable pantry stock, disclose that meal prices are unavailable, and leave pantry/list state unchanged. This is synthetic source/runtime evidence, not a production deployment. Missing conversions and unsupported recipe fulfillment flags fail closed before writes; ambiguous recipes still ask first. Disposable Alpha owner UI now passes serving preview → same-chat confirmation → canonical read-back → fresh preview → cancellation; the authenticated Alpha/Beta deferred-search UI also passes, with owner URL/authoring tools hidden from Beta and raw serving mutation denied before dispatch. The test dismisses Open WebUI's user-dismissible update notice that otherwise overlaps the composer. Real household data remains review-gated. | No synthetic owner-browser blocker remains. Keep real household content review-gated and raw serving mutation behind deterministic owner confirmation. |
| Shared Channels candidate promotion | Candidate isolation, restart persistence, live feature configuration, and preserved-owner private-channel create/post/read/delete acceptance pass on VM 802. | Keep Channels private/owner-scoped; do not transfer Hindsight or owner authority through membership. |
| Homelab read-only | Proxmox and NetBox least-privilege read-only inputs are provisioned; live owner dogfood separates GPU inventory from runtime liveness and invokes the bounded current-LAN scan without writes. NetBox contains seven physical/observed records and Kuma publishes 11 LAN-scoped monitors; VM 802 is live but its NetBox intended-inventory record and two Kuma destination monitors remain plan-only pending authoritative address reservation. Read-only refresh 2026-09-26 covered all six physical hosts: Tartarus and Hypnos are reachable, but NVIDIA 615.71.09 rejects their Quadro P4000 devices; no NVIDIA module/device nodes load and `nvidia-smi` fails. NVIDIA documents P4000 under the 580.xx legacy branch. No driver, host hardware, or VM guest state changed; Proxmox read-only token ACLs are reconciled below. Hermes is reachable with NVIDIA 590.48.01 loaded and both RTX 2080s visible; a further read-only check found Docker active but zero containers (including stopped) and no Ollama/llama/vLLM service or matching listener, so there is no container workload on which to verify GPU injection. Thanatos has `nouveau` loaded and NVIDIA unavailable; Secure Boot/driver policy remains gated. Alexandra's GTX 660 has no IOMMU group. Erebus' P4000 is bound to `vfio-pci` with IOMMU groups present, but running VM 802 has no `hostpci` entry. `/dev/sdd` has a historical SMART anomaly; `.113` is an excluded Sony PS5, not a server. | In an approved maintenance window, restore the supported 580.xx legacy driver on Tartarus/Hypnos and retest native CUDA/reboot persistence; qualify a real Hermes inference workload before testing container GPU injection and reboot persistence; resolve Thanatos firmware policy and `/dev/sdd` follow-up; resolve Alexandra IOMMU and whether Erebus GPU should be assigned; locate the seventh server, finalize the VM 802 address reservation, and apply plan-only NetBox/Kuma updates through their operator surfaces. Keep discovery review-only. |
| Home Assistant read-only | No approved URL, token, entity allowlist, or exposure path is configured. | Approve the selected read-only entities and provide the scoped token/path. |
| Real finance | Natural-language statement inspection and write-free Actual previews are DOGFOOD GREEN; production finance mutation remains intentionally inactive. | Approve the Actual Budget environment/budget, historical imports, retention, secret storage, destination-account policy, and later live-sync provider. |
| Encrypted off-host recovery | Encryption key custody, off-host destination, retention, and plaintext-retirement policy are not selected. | Provide an operator-managed key and destination policy. |
| First real household user | Household Alpha is ready; onboarding needs the chosen real identity and credential flow. | Owner supplies or authorizes the intended identity/invitation. |

## Independent technical work status

- **Minecraft self-service preflight and lost-plan continuation (production UX defect):** A strict-host-key, read-only inspection of the live Hermes process on 2026-09-28 found only `linux-sandbox:853` in `HADES_PROXMOX_TEMPLATE_MAP`, with no Minecraft alias. Local tracked source now checks the approved template and placement catalog before persisting a request, returning a no-change refusal if either is absent. Pinned Hermes runtime and authenticated disposable Alpha UI acceptance pass with an unconfigured catalog. The full tracked continuation/plan fix is not deployed; active overlay provenance remains unresolved. A narrow guard is deployed on the exact active overlay to refuse this lost-plan Minecraft continuation before model or provisioning calls while no Minecraft alias is configured. Tracked source also now treats a successful Proxmox start as VM readiness only: it explicitly does not claim Minecraft is running or provide an IP/firewall endpoint, and it hides adapter error details while telling users not to retry unknown or partial outcomes until reconciliation. Pinned Hermes and authenticated disposable Alpha UI acceptance pass for VM-only readiness wording, no firewall/IP claim, unknown-outcome non-retry guidance, and no raw backend error disclosure. The UI test uses a loopback Proxmox fixture and disposable registry; it is not live Minecraft or production acceptance. Production now contains only that narrow no-template continuation guard; no VM or firewall state changed. The live Hermes service is active and healthy with overlay SHA-256 `d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`. The owner repeated the exact dogfood on 2026-09-28 and again on 2026-09-29: after HADES offered to show an approved bounded plan, “Perfect, continue” fell through to a generic greeting. Current tracked source has a transcript-recovery path for this exact wording and its pinned Hermes contract passes, but the observed production failures confirm the running copy still lacks or does not execute that path; request-to-worker causality remains unproven. No VM/server was created and no firewall change occurred in either dogfood. Production remains unconfigured for a HADES-managed Minecraft template/placement, so this chat cannot provision a new HADES VM or provide its guest IP. Separately, the existing vanilla Minecraft container on Thanatos was freshly verified healthy at `<PRIVATE_LAN_ADDRESS>:25565/tcp`; direct Java status returned version 26.3, protocol 777, 0/10 players. The existing Prominence II service is at `<PRIVATE_LAN_ADDRESS>:25566/tcp` (Minecraft 1.20.1/protocol 763) and requires the matching client pack. Neither service was created by the chat; external router/firewall forwarding remains unverified. The HADES adapter cannot establish Minecraft protocol readiness or read back a newly provisioned guest IP. Generic server wording is clarified, unsupported Factorio/Palworld templates are rejected, and mixed workload requests ask the user to choose rather than silently selecting Linux sandbox.


- **Reconstruction missing Open WebUI upload assets (source fixed; production untouched):** The Open WebUI Compose template bind-mounts finance and receipt upload JavaScript, but the installer, reconstruction manifest, doctor, and validator did not stage or require those files. A clean rebuild could omit working finance/receipt UI assets. Commits `897166f` and `f91b0db` add both assets to install staging and layer digests, require them in validation/doctor, and make CI compare every config asset mount against the reconstruction manifest. The clean-archive synthetic fixture and finance/receipt contracts pass, including doctor rejection when a required mount asset is removed. VM 802 already has upload assets; this is a rebuild defect, not a live-service change. No production file or service changed.

- **VM 802 provenance follow-up — 2026-09-29:** A fresh strict-host-key read-only check confirmed the active service command line `/opt/hades-hermes-0.21.2/venv/bin/python -m hermes_cli.main -p hades gateway run --quiet`; the unit has no `HADES_HERMES_EXECUTABLE`, while the installed `hermes-agent` distribution reports 0.21.2. The active template map remains only `linux-sandbox:853`. Running Git as root first hit Git's dubious-ownership guard; rerunning read-only as `scotty` confirmed checkout `b102dfdf42fc564c040c432cb2c6e87ee1f27d22` with 35 tracked/untracked status entries. Active overlay remains `d827e9db…`; the endpoint still serves the 2026-09-24 `bcd81f4` / `1863ed…` record. A bounded AST comparison against tracked overlay SHA `75c53a39…` found 42 of 64 active top-level functions byte-structure-equivalent, 22 with changed bodies, 34 tracked functions absent, and no active-only function names; the missing continuation helper is not present in the active artifact. A scan of all 417 committed overlay revisions maps 62/64 active function bodies to Git history; the remaining `_hades_task_response` and `_hades_nonpersonal_state_turn` match protected deployment backups, not tracked source. This accounts for function origins but not a clean, reproducible composed overlay. The provenance writer now supports this legacy Python-module launch and verifies package version, interpreter path, and active process identity. Focused synthetic contracts pass. No live record, service, checkout, VM, Minecraft server, or firewall was changed.

- **P2: household onboarding and identity-aware restore:** Guest C exposed two defects: first-use Hindsight banks were missing, and persisted Open WebUI `openai.api_configs` omitted the stable Hermes session header. Tracked source lazily creates banks from trusted authenticated scope/subject, the compose template seeds `X-Hermes-Session-Key: hades-user-{{USER_ID}}`, and `hades-doctor` checks the header. Fresh-volume Alpha/Beta/Gamma authenticated Hindsight UI passes retain, correction, fresh recall, persistence, and isolation. First LDAP login also created Beta/Gamma as `pending`; after verifying their `hades-household` membership, synthetic Alpha admin promoted them to ordinary `user` and granted each read access to `hermes-agent`. An isolated restore of Guest C's latest SQLite snapshot and matching Hindsight archive then passed LDAP login, stable subject/role mapping, model visibility, authenticated per-user conversation history, Alpha settings persistence across Open WebUI restart, and raw Hindsight bank isolation (five tagged Alpha records; zero Beta/Gamma records). The raw archive retains both historical mango and corrected pear, so restored authenticated Hermes recall freshness is still unproven. Hermes itself, Grocy, Agent Zero, and SearXNG were not restored in that replay; whole-HADES/whole-guest restore and independent Guest B remain open. Production was not changed.


- **P2: transient over-scoped Proxmox token read (contained):** During repair
  of the separated read-only API tokens, a validation ACL briefly exposed
  guest summary rows beyond the approved target set. One direct
  `/cluster/resources` response returned only guest type, node, and VMID
  metadata for those additional guests; no configuration, console, guest
  filesystem, or application data was requested. The broad ACL was immediately
  removed and replaced with per-token guest paths; a fresh request returned
  only the approved HADES/Services guests. No VM workload state or HADES
  service was changed. No owner request was initiated during the brief window;
  a concurrent application read was not independently ruled out. The scope is
  now contained; retain this note as the audit trail.

- **Network-slow question (bounded synthetic coverage):** The ordinary
  owner-language prompt asking what looks abnormal when the network feels slow
  now has deterministic Hermes runtime and authenticated disposable UI
  coverage. When Uptime Kuma supplies a fresh bounded numeric `ping_ms`, the
  read-only route reports it as an individual configured-probe response-time
  sample. It also combines current Proxmox data and failed probes, explicitly
  states that packet-loss, throughput, and historical comparison are
  unavailable, and refuses to assign a network-wide bottleneck or trend. The
  tests make zero model calls and preserve pending Task state. This is synthetic
  evidence; no production prompt or host was queried. Live telemetry still does
  not establish a complete network diagnostic.

- **Compound server and backup status (synthetic runtime PASS):** An owner
  asking “Are all the servers okay, and what backup coverage do I have?” now
  receives both the bounded live server summary and the current Backup Check
  coverage, with plain section labels. An authenticated disposable Alpha browser
  run confirms both sections persist in chat and the answer accurately limits
  coverage to the seeded HADES repository check. This read-only composition is
  owner-only, makes zero model calls, and leaves Task state unchanged. Pinned
  Hermes runtime coverage exercises both injected sources and the actual
  synthetic homelab and backup adapters; household scope and action wording stay
  outside this shortcut. Production was not queried.

- **Named physical-node status phrasing:** A speech-like owner question,
  `whats tartarus doing rn`, now stays on the deterministic read-only route.
  If the node is present only in the observed hardware inventory, HADES gives
  its recorded address/role and says it has no current runtime check; it does
  not imply that Proxmox manages the physical host or claim that it is online.
  If a physical host instead has a matching Uptime Kuma row but no Proxmox
  runtime, current source reports only the named probe's fresh/stale result
  and explicitly avoids presenting that probe as host workload or operating-
  system health.
  The pinned Hermes runtime contract and authenticated synthetic Alpha UI pass
  for fresh-up, fresh-down, stale-up, and inventory-only physical-node cases.
  The responses persist in authenticated chat history, make zero model calls,
  and leave Task state unchanged. This is synthetic inventory and monitor
  evidence, not a live Tartarus application check; production was not queried.

- **P1: production cross-chat confirmation isolation (reproduced on active overlay):** Read-only
  refresh on 2026-09-28 copied the active overlay from VM 802 under strict
  host-key verification and confirmed SHA-256
  `d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`.
  The original focused probe used different initial prompts in the two chats
  and therefore missed a collision in the legacy prompt-derived identity.
  After strengthening `scripts/test-confirmation-conversation-hermes-runtime.sh`
  so both synthetic chats begin with the identical `Run Backup Check.` request,
  the exact active bytes under pinned Hermes 0.21.2 consume Alpha's synthetic
  pending confirmation when Beta replies `yes`; the stub returns
  `SYNTHETIC_BACKUP_CHECK_EXECUTED`. It makes zero model/API calls and executes
  no real workflow. Current tracked source passes this stronger cross-chat
  case, missing-chat-ID refusal, and same-chat decline. The active artifact
  remains a confirmed P1 bypass; no production confirmation or workflow was
  attempted. A clean `git archive` of HADES `4e04ee5` (overlay SHA-256
  `75c53a39…`) passes the focused confirmation, Minecraft continuation,
  Grocy tool-scope, and Task/homelab Hermes runtime suites. This is a
  source-bound, reproducible candidate, not full production acceptance; it
  does not reconcile or replace the mixed active overlay. No deployment was
  performed. Additional clean-archive packaging contracts pass for exact
  overlay drift detection, manifest provenance, generated deployment records,
  install ordering, partial-install recovery, and fail-closed missing/unsafe
  private inputs. The HADES installer copies the canonical overlay and binds
  its digest into the generated install contract. The current clean-archive
  synthetic fixture also passes isolated-root test-mode install, validator,
  non-mutating doctor, Compose/systemd parsing, secret modes, reconstruction
  manifest, and full installed-layer digest checks. This is not clean-host or
  production acceptance. A fresh non-mutating doctor run on VM 802 using its
  generated operator input exits nonzero with exactly one failure:
  `HADES layer provenance is stale`; installation-marker and reconstruction-
  manifest provenance checks pass. No secret values were printed.
  Read-only per-file hashing then showed the install marker records clean
  source layer `fcd5e1ed…` from HADES `c3f7262`, while the running checkout
  expects `a49c64c2…` and the installed files hash to `9e5f7600…`. The two MCP
  adapters match the running checkout; the CSS matches current local HADES
  HEAD, the JS matches historical `cdf18cc`, and the active overlay is a
  different mixed artifact. No single reviewed commit currently identifies
  the installed five-file layer.
  The independently reported Minecraft context-free “Perfect, continue” path
  remains a current-artifact defect: the same active SHA `d827e9db…` called the
  isolated model endpoint once instead of refusing before inference. No VM,
  firewall, user, task, or production service was changed during these checks.
  The earlier read-only observation on 2026-09-28 found VM 802 running overlay SHA-256
  `40f37c7be0c12e0df552148a8d5cab098f26ef8ecb7b767c39a14621fed55759`; the
  service is active. The deployed `_hades_turn_identity(user_text, history)`
  helper and its route both use two arguments, so the earlier reported
  signature mismatch was incorrect. The actual defect is an actor-wide
  `_early_candidates` fallback: when a follow-up has no chat-matched pending
  action and the actor has exactly one pending typed action, the route reuses
  that action without confirming it came from the current chat. A bare
  affirmative in another chat can therefore consume the pending operation.
  No authenticated production confirmation was attempted and no production
  state was changed.
  At that earlier observation, strict-host-key read-only inspection confirmed
  the active overlay SHA and two-argument identity helper. A local mode-0600 copy
  of those exact active bytes was exercised with synthetic SQLite state and a
  stub runner: a pending Backup Check in Chat Alpha followed by bare “yes” in
  Chat Beta invoked the stub, consumed Alpha's pending item, and returned its
  synthetic completion marker. The stub made zero network calls and ran no
  workflow. This is an exact-artifact runtime reproduction with synthetic
  state, not a production user action or workflow execution. The same current
  source runtime test passes the cross-chat refusal, missing-chat-ID refusal,
  and same-chat decline cases; it makes zero model calls and preserves the
  pending item on refusal. This reproduced the confirmation-boundary defect on
  the then-active `40f37c7b…` artifact; the later `d827e9db…` artifact passes
  the focused current-artifact regression described above. The only consumed
  operation was synthetic state in the local test; no production state was
  changed.
  A fresh AST/body scan of that `40f37c7b…` artifact across 383 repository
  revisions matches 111/116 callable bodies; five remain unattributed. The
  artifact also fails the owner-serving preview in the exact pinned scope
  runtime. Both gaps keep deployment gated even though current source passes
  the cross-chat runtime contract.
  Current tracked source and the review candidate bind confirmation state to
  the server chat and fail closed when identity is missing. A new combined
  review candidate (`c09ea81a…`) passes the focused confirmation contract and
  the authenticated synthetic two-chat UI: cross-chat confirmation is denied
  with no model calls or state change, and same-chat decline clears only its
  pending item. Its eager/deferred/direct recipe-scope checks also pass. The
  broader current Grocy harness reaches an owner-serving flow not present in
  the older deployed base; a fresh full synthetic run with candidate
  `c09ea81a…` fell through to the model (`UNEXPECTED_MODEL_INVOCATION`) before
  presenting its deterministic, write-free serving preview. AST inspection
  found the candidate lacks `_hades_recipe_servings_adapter`,
  `_hades_recipe_serving_intent`, `_hades_recipe_servings_response`, and their
  call from `_hades_run_conversation`, all present in current repository
  source. The synthetic Grocy API was not mutated. Full combined regression
  coverage is incomplete and the candidate remains review-only. Deployment
  remains separately gated. The provenance endpoint
  still reports the stale 2026-09-24 artifact `1863ed…`, and the active overlay
  is not established as canonical tracked source. No live user confirmation or
  recipe data was accessed.

  Follow-up synthetic review: a disposable source-composition candidate was
  assembled from `c09ea81a…` plus the current recipe-serving route and the
  preemptive Grocy decline helper. Its exact temporary SHA-256 is
  `0c9fd633973a936bde0f52e050056ee1b3a711326d6f24a1d9614f8fd293baf8`.
  Against this candidate, authenticated owner serving preview/confirmation,
  household denial, cross-chat isolation, same-chat cancellation, one
  canonical write/read-back, and the deferred recipe tool-catalog boundary
  pass on disposable Alpha/Beta data. The focused test harness now skips its
  unrelated shopping-list decline-log assertion in owner-serving-only mode;
  the full household scenario still checks that behavior. This does not make
  the composed artifact canonical: broader regression coverage and exact
  production overlay provenance remain unresolved, so no deployment is
  justified. The corrected owner-serving-only harness has since passed against
  current HADES source, and the full authenticated synthetic Grocy household
  UI also passes with the independent shopping-list decline assertion retained.
  A corrected full-AST comparison (including callables nested beneath
  module-level conditionals) confirms the temporary serving review artifact has
  119 callable nodes. Of these, 104 bodies match tracked HADES history; versus
  the current worktree it has 95 exact bodies, 23 changed bodies, one
  candidate-only body, and 24 current-only bodies. It is useful for its focused
  passing cases but is not full overlay equivalence.

  **Updated full-suite result (2026-09-27):** A later temporary composition at
  `/tmp/hades-combined-full-grocy-review-laolvy_3/sitecustomize.py`, SHA-256
  `1ee2c1ca49651c043b82bfc0df50a38e09660eea49f93373da1e4827a502d60f`, passes
  `scripts/test-grocy-authenticated-household-ui.sh` with
  `HADES_GROCY_UI_INCLUDE_OWNER_SERVING=1`, plus
  `scripts/test-confirmation-conversation-isolation.sh` against that exact
  source. The full run exposed and the temporary composition then closed stale
  household meal-budget denials, expired-food recipe overlap, a missing
  natural-language shortage-add call site, and product-ID name resolution in
  shared-list reads. This is synthetic review evidence for that temporary
  composition; it does not supersede the active-overlay provenance gap below
  or justify deployment.

  **Task/homelab regression update (2026-09-27):** Extended that temporary
  composition with current owner Task attention/briefing behavior, the
  natural-language attention matcher, homelab blocker/service-monitor
  composition, and the ambiguous entertainment-device clarification. The
  resulting SHA-256 `da4fdf8d71783ade052a51eba07ba52474c719494adca56bc5972c5d08f0f928`
  passes `scripts/test-task-chat-hermes-runtime.sh` (including owner/household
  isolation and zero-model-call assertions), the full authenticated synthetic
  Grocy household UI with owner serving enabled, and the confirmation
  conversation-isolation contract. This strengthens the review candidate's
  functional coverage but does not establish canonical source equivalence or
  resolve the active production overlay's two unmatched function bodies.

  **Task notification UI update (2026-09-27):** Added the current
  actor-scoped, read-only Task notification feed and route to a later review
  candidate, SHA-256
  `cb67d02f9a77ad028fd42ccaa9257781895be48902364ce3234d2b3f325cf3a4`. Its
  authenticated synthetic Alpha/Beta/Gamma UI passes notification isolation,
  no-store, 401/403 clearing, transient-503 preservation, desktop delivery,
  and state-immutability checks, plus the Task runtime, Grocy household, and
  confirmation contracts. `scripts/test-task-attention-authenticated-ui.sh`
  now accepts `HADES_HERMES_OVERLAY_DIR` for exact-candidate runs. Production
  notifications remain inactive: VM 802 lacks the required notification
  environment keys, and active-overlay source provenance is still unresolved.
  No production request or change was made.

  **Review-candidate freshness recheck (2026-09-27):** Re-running the current
  full authenticated Grocy/owner-serving harness against exact candidate
  `cb67d02f…` exposed an omitted compound recipe/expiry route call site. It
  returned canonical expiry details but omitted the named recipe's shortage;
  the synthetic run stopped before owner-serving assertions. The candidate
  contains the helper but not its call from `_hades_run_conversation`, so it is
  stale against the current harness and is not a full-composition candidate.
  The same current full harness against tracked HADES source passes, including
  owner serving, confirmation isolation, household denial, and canonical
  synthetic Grocy read/write/read-back. The disposable API/UI stack was cleaned.
  This is review-artifact drift, not a current-source product regression.

  The exact deployed scope-hotfix bytes were re-read from VM 802 and still hash
  to `40f37c7be0c12e0df552148a8d5cab098f26ef8ecb7b767c39a14621fed55759`
  (`root:hades-runtime`, mode `0644`; unit active, zero restarts). A recursive
  full-AST scan maps 105 of 114 callable nodes to tracked HADES bodies. The
  nine unmatched nodes are `_hades_agent_init` and its three nested bridge
  helpers, `_hades_filter_tools_for_scope`, `_hades_task_response`,
  `_hades_nonpersonal_state_turn`, `_hades_prefetch`, and
  `_hades_run_conversation`. The task and nonpersonal-state functions match
  protected production-backup bodies exactly; the filter helper and three
  nested bridge helpers match the preserved current worktree source. The agent
  initializer is a documented patch on a tracked base. `_hades_prefetch` and
  `_hades_run_conversation` remain the two source bodies without an independent
  tracked or local source copy. The exact active file is still not fully
  reproducible from tracked repository source.

  The previous active overlay SHA-256 was
  `7827093c071aa05c5792b5c8213d951a2a75df83e4b73965ab5da46e72d2f093`; its
  exact bytes remain preserved in the protected VM rollback backup. The
  currently deployed scope-hotfix overlay is `40f37c7b…`. The focused runtime
  harness now accommodates both the deployed two-argument and tracked
  three-argument identity-helper generations. Current tracked source passes.
  With `HADES_EXPECT_CROSS_CHAT_CONFIRMATION_BYPASS=1`, it can also assert the
  expected vulnerable result on an explicitly supplied artifact. Re-read
  production bytes at SHA-256 `40f37c7b…` produced the synthetic completion
  marker and consumed only the synthetic pending item; no workflow or network
  call was made. A
  separately composed candidate at SHA-256
  `a2ec1740579791596072c4e16dac28728f1f5c6b46f37cc1cdee22d304088c86` passes
  both the focused Hermes runtime and authenticated synthetic Alpha UI checks;
  it remains review-only and has not been deployed. The recovered active bytes
  are not yet canonical tracked source. The scope-only hotfix is deployed;
  confirmation-path changes remain separately gated.

  Revalidation of the preserved candidate bundle on 2026-09-26 again passed
  the focused Hermes runtime test and authenticated two-chat Alpha UI test.
  A fresh AST scan over all 313 tracked revisions confirms four exact active
  function bodies have no Git source match. The candidate changes seven
  function bodies relative to that active artifact: three map exactly to
  tracked revisions (`_hades_overlay_non_hermes_interpreter`,
  `_hades_pending_provision_keys`, `_hades_turn_identity`); four do not
  (`_hades_agent_init`, `_hades_phase2_backup_response`,
  `_hades_phase3_response`, `_hades_run_conversation`). It also retains three
  other unmatched active bodies (`_hades_nonpersonal_state_turn`,
  `_hades_prefetch`, `_hades_task_response`). The active/candidate task response
  digest is `044452f81202e3d1` versus `bb2fbdbc4ede0016` in current tracked
  HADES; the candidate run-conversation body is also unique. Its manifest pins
  context to HADES `e7de22e`. Thus the candidate remains evidence for the
  narrow chat-isolation behavior, but seven candidate bodies lack exact Git
  source identity; it is not a current-source release candidate. Rebuild the
  component source map before any deployment decision.

  A new read-only VM 802 refresh at 2026-09-26 23:16 UTC reconfirmed active
  overlay SHA-256 `7827093c…`; the provenance endpoint still reports the old
  `1863ed…` overlay and has no HADES/infra revision. A line-exact function-body
  scan over all 313 tracked revisions maps 109 of 113 active functions; four
  remain unmatched: `_hades_task_response`, `_hades_nonpersonal_state_turn`,
  `_hades_prefetch`, and `_hades_run_conversation`. The current committed
  repository overlay maps all 133 function bodies to tracked Git history. The
  separate `0c1abb2d…` file is not active; its 106 functions all map to tracked
  history, but it is a different composition and cannot establish deployed
  provenance. On the exact recovered `7827093c…` bytes, the pinned synthetic
  Hindsight route runtime passed fresh retain/recall, latest correction after a
  two-word typo, paraphrase fallback, and Alpha/Beta isolation. This isolates
  that bounded synthetic memory workflow; it does not close the four-function
  source map, prove production data outcomes, or establish a production latency
  SLO. No production memory or service was changed.

  **Exact-artifact scope/serving recheck (2026-09-26):** Re-ran the registered
  eager/deferred/direct-executor scope contract against the exact deployed
  scope-hotfix bytes (`40f37c7b…`). Those checks pass, but its owner-serving
  route falls through to the synthetic model instead of returning the current
  deterministic preview. Current repository source passes the same scope
  contract. A separate review artifact (`cb67d02f…`) passes the scope and
  cross-chat confirmation runtime contracts, the authenticated owner-serving
  preview/confirmation/cancellation journey, and the full authenticated
  Alpha/Beta/Gamma Grocy household journey with owner serving enabled. The
  authenticated harness now supplies its explicit Hermes working directory so
  an overlay outside the checkout can resolve the packaged serving adapter.
  A recursive callable-body comparison against all 313 tracked overlay-file
  revisions maps 117 of the candidate's 137 callable instances to exact
  tracked bodies; 20 instances have no tracked-body match. It maps 121/137 to
  the current dirty worktree and 107/137 to current HEAD. No tracked revision
  contains the candidate as an exact whole-file blob. The review artifact is
  therefore a tested but unreconciled composition, not a reproducible
  release candidate. Production remains read-only and the active source
  provenance gate remains open.

  **Hotfix update (2026-09-28):** After a fresh hash check confirmed the active
  overlay still matched `40f37c7b…`, a minimal patch removed only the
  actor-wide `_early_candidates` recovery. The patched artifact is the exact
  active file plus that one deletion (SHA-256
  `25c85b9d89c637be046cea5adeaa1e627836b7344734ecfd769d02acb0f7a7c6`). The
  focused pinned-Hermes regression passed against those exact candidate bytes
  before activation. It was installed atomically and only
  `hades-hermes.service` was restarted. Post-checks: service active, zero
  restarts, effective `PYTHONPATH` selects the patched overlay, `/health` HTTP
  200 on the configured bridge listener, and active SHA matches the tested
  candidate. The original overlay remains available as a `root:root` mode-0600
  rollback copy with its original SHA verified. No real operation, VM,
  firewall, provider, or user data was touched. This closes the cross-chat
  actor-wide confirmation defect in the active artifact. The five-body source
  attribution gap and owner-serving mismatch remain open; the provenance
  endpoint still needs reconciliation. This targeted security hotfix does not
  deploy the separate Minecraft plan-recovery/template changes.

- **Server Health Watch cross-worker confirmation precedence (repository and
  authenticated synthetic UI fixed/verified; production update pending):** The route contract covers both stale-cache
  directions: a worker-local create preview cannot override a newer persisted
  share action, and a worker-local share action cannot override the current
  persisted create preview. `scripts/test-health-watch-hermes-runtime.sh` now
  drives both cases through the pinned Hermes `AIAgent.run_conversation`
  wrapper with synthetic state, zero model calls, no duplicate automation,
  and no unintended share mutation. The operation-level state remains
  conversation-scoped. The new `scripts/test-health-watch-cross-worker-authenticated-ui.sh`
  drives an authenticated Alpha Open WebUI conversation across two isolated
  Hermes workers: create preview on A, share preview on B, and bare `Yes` on A.
  The same conversation persisted all turns; canonical synthetic SQLite ended
  with exactly one watch shared to Beta and no stale duplicate. The local
  router confirms the A/B/A worker sequence through one visible model. This is
  synthetic browser acceptance, not owner acceptance. The active production
  overlay still requires a separately authorized update and post-change
  acceptance; production was not contacted in this work.

- **Weekly partial-result sharing:** A new synthetic integration and authenticated
  Alpha/Beta/Gamma Open WebUI run covers one partial household result end to
  end through `compose_summary`, bounded `SummaryHistory`, the Hermes history
  route, and the authenticated chat. When Grocy fails, Alpha and the explicitly
  shared Beta receive the unavailable Groceries disclosure plus healthy Server
  and Backup sections; unshared Gamma sees only the no-shared-summary response.
  Retrieval does not mutate the stored result. This closes the synthetic
  per-recipient partial-history gap. The authenticated mode was rerun on
  2026-09-26: Alpha and authorized Beta received the same partial result and
  Gamma received only the unavailable-share response. Report:
  `/tmp/hades-task-attention-1877292.json` (mode 0600). A separate disposable
  run of the pinned n8n image now executes this exact weekly workflow with the
  Grocy source returning synthetic HTTP 503; n8n completes, preserves the
  failed Grocy result, and still receives healthy Backup and `UP` health
  results exactly once. This verifies the live n8n source-failure branch, not
  production or the not-yet-wired scheduled delivery into Open WebUI. No
  production dependency was disabled.

- **Persistent Task browser alerts (synthetic acceptance PASS; production
  inactive):** The disposable Alpha/Beta/Gamma browser flow verifies
  actor-scoped, deduplicated alerts, an unsent review prompt, and clearing
  Alpha's alert when the same browser switches to Beta. A read-only production
  inspection found the Open WebUI route and theme asset installed, and its
  unauthenticated route returns HTTP 401. The required Task-notification
  Hermes URL/key inputs are absent, and the active Hermes overlay does not
  implement the Task-feed request marker. Therefore the authenticated feed is
  not wired and no production Task alert is available. No authenticated
  production feed request or Task read was made. Complete canonical overlay
  source reconciliation before enabling the inputs; keep production unchanged
  until that gate and post-change acceptance pass. A separate source-only
  authorization-loss repair now clears the current user's in-page/desktop
  alert, notification cursor, and queued review prompt on 401/403, while
  retaining them for transient 503 responses. A delayed prior-user 401 is
  prevented from dismissing the current user's alert after an account switch.
  A request-generation guard prevents a successful response already in flight
  from restoring notification state after authorization has been lost.
  The current-source theme has now passed the full authenticated Task
  attention UI in a uniquely rebuilt Open WebUI image, including stale Alpha
  401 after switching to Beta, Beta's private alert remaining visible,
  transient-503 preservation, current-user authorization clearing, desktop
  notification closure, and synthetic Task state restoration. The same
  acceptance includes household status, attention, and media-device journeys.
  The synthetic desktop Notification API confirms the close call occurs.
  This does not activate or deploy the production notification feed. Report:
  `/tmp/hades-task-attention-2977779.json` (mode 0600). A 2026-09-27 read-only
  VM 802 refresh reconfirmed the active Hermes scope-hotfix hash
  (`40f37c7b…`), healthy Hermes 0.21.2 service, and absence of both
  Task-notification environment-variable names in the Open WebUI container;
  no authenticated feed request or Task data was read.

  **Phase 3 result-alert account-switch race (2026-09-27):** A delayed 403
  response from Alpha's old browser poll could clear Beta's currently visible
  Phase 3 alert after the same tab switched accounts. The poll now captures an
  authorization epoch and only clears the notification surface when the
  rejected response still belongs to the current account/epoch; stale
  successful responses also cannot update its cursor. The authenticated DOM
  harness now holds Alpha's request, switches to Beta, creates Beta's own
  synthetic alert, and releases Alpha's 403; Beta's alert must remain visible.
  The regression first reproduced against the stale cached WebUI image, then
  passed in the full joined Phase 3 acceptance against a uniquely built image
  from the current Dockerfile/theme: signed n8n due/run, one synthetic source
  call, service restart and duplicate-delivery idempotency, Alpha/shared-Beta
  result visibility, unshared Gamma denial, notification review prompt, and
  immediate Beta revocation. Report files and disposable runtime state were
  removed; temporary image cleanup and unchanged Docker volume count were
  verified. Production inputs/schedules remain inactive; no production request
  or change occurred.

  A follow-up extends this path through recovery: when Beta's latest
  authorized result becomes healthy, the old in-page alert is removed while
  still-active source alerts remain visible. The joined current-source
  browser/runtime acceptance passes this recovery transition. The code also
  tracks desktop alerts by source and closes a tracked alert when a later
  authorized snapshot reports recovery or a changed state.

- **Hindsight freshness and latency:** A production fresh-conversation recall
  once returned an older same-user synthetic marker. The recorded bounded
  overlay update (`0c1abb2d…`) was followed by a successful authenticated
  fresh-recall smoke after restart (33.1 seconds from retain to recall success;
  66.3 seconds total). This is one successful smoke, not a production SLO or
  exact typo/correction acceptance. The current repository adds a bounded
  tagged-memory lookup before semantic recall; a strong same-bank match skips
  semantic recall, while unmatched paraphrases retain semantic fallback. The
  source, actor isolation, correction, typo, and paraphrase paths pass against
  the pinned Hindsight image; this latency optimization is not deployed. A
  disposable authenticated Open WebUI acceptance now also passes synthetic
  Alpha retain/correction/fresh typo recall and Beta/Gamma private-bank
  isolation through the Hermes 0.21.2 gateway. This validates local source;
  production was not touched. A fresh aggregate-only read across all 13
  production banks found 3 pending / 470 failed operations and 52 pending /
  1,118 failed consolidations; all 52 pending consolidations are reported by
  one bank, whose identity was not recorded. A newer aggregate-only refresh
  at 2026-09-26 17:24 UTC queried the same 13 banks and confirmed 3 pending /
  470 failed operations and 52 pending / 1,118 failed consolidations. The
  earlier 38-pending sample is historical; aggregate counts can vary between
  reads. No bank names or operation rows were retained. A 24-hour log-pattern summary
  found six worker claim batches and no claimed consolidation tasks, worker
  error/exception patterns, or common provider-failure patterns.

  The running Hindsight worker process is present, but its container lacks
  `HINDSIGHT_API_WORKER_ID`; the generated production Compose file also lacks
  the stable ID that the tracked template declares as `hades-hindsight`.
  Consequently the existing read-only worker-identity check would fail for
  production. This is a confirmed deployment drift and a plausible contributor
  to stranded processing work, but it does not prove the consolidation backlog
  cause. Disposable pinned-image recovery tests pass: a stable worker ID
  reclaims its own processing row, while foreign-worker and synthetic
  previous-container-ID rows remain untouched. This reproduces the stale-ID
  stranding mechanism but does not identify the owners of production rows. Do
  not inspect operation details, retry, replay, or delete production work until
  worker ownership and safe recovery are established.

  `scripts/test-hindsight-ephemeral-worker-recreation.sh` further reproduces
  the default-ID failure boundary on the pinned image: after an abrupt
  disposable container loss, recreating the same service with a new default
  hostname leaves the old worker's processing row untouched; explicitly
  restoring its original ID returns only that synthetic row to `pending`. A
  graceful stop is intentionally excluded because Hindsight releases its own
  work on shutdown. This confirms the mechanism under synthetic conditions,
  not the worker ID or cause of any production row.

  A read-only VM 802 refresh on 2026-09-26 confirmed the pinned API is still
  healthy (`/health` 200, API `0.9.2`), running for about 45 hours with zero
  container restarts. Its process metrics show a zero-waiting DB pool. The
  worker still has no configured `HINDSIGHT_API_WORKER_ID`; its startup log
  used a container-derived ID. Aggregate stats across 13 banks are unchanged:
  3 pending / 470 failed operations and 52 pending / 1,118 failed
  consolidations. No operation rows were read, retried, replayed, or deleted;
  no production service or memory was changed. The worker-identity mismatch
  remains a confirmed configuration defect and plausible backlog contributor,
  not a proven explanation for each stale item. The staged, non-authorizing
  change and rollback sequence is documented in
  [`docs/hindsight-worker-identity-recovery.md`](hindsight-worker-identity-recovery.md);
  it distinguishes stabilizing future worker ownership from recovery of
  existing rows whose owners are unknown.

- **Canonical Grocy write recovery:** The normal shared shopping-list add
  already uses a cross-process lock around its canonical re-read/write. The
  owner spaghetti recipe action had an independent check-then-write race; its
  source now serializes recipe creation and ingredient reconciliation, and
  shares the shopping-list lock for missing-item inserts. A two-process
  synthetic Grocy runtime test proves one recipe, five ingredient positions,
  and one row per missing item. The live VM 802 overlay still contains the
  previous unlocked recipe path; this source repair has not been deployed or
  accepted in the authenticated UI.

- **Household generic recipe creator authorization (source and scope hotfix pass; authenticated live acceptance open):** The synthetic Alpha/Beta authoring journey found that the shared Grocy MCP exposed generic `recipe_create_tool` to the household catalog even though the dedicated authoring server was hidden. Household scope now removes that generic creator from eager and deferred catalogs, and raw deferred `tool_call` is rejected before dispatch. The pinned Hermes scope runtime test and authenticated Alpha/Beta browser flow pass; Beta receives a plain owner-only denial and produces no recipe write, while Alpha still creates/edits/restores and verifies canonical state. The deployed VM 802 overlay `40f37c7b…` contains these runtime gates, and registered synthetic executor tests pass. An authenticated live household catalog was not queried; live acceptance and canonical provenance remain open.

- **Household expiry and recipe suggestions:** A disposable authenticated
  Beta UI regression found that meal suggestions treated any dated stock row
  as “expiring,” including food due weeks later and already-expired food. The
  read now suggests saved recipes only from nonexpired ingredients due within
  seven days; expired food is not used as a meal suggestion. The ordinary
  “What's going bad soon?” phrasing routes to canonical Grocy metadata.
  Authenticated synthetic coverage distinguishes near-expiry eggs, later-dated
  milk, and expired bread; production remains unchanged.

- **Backup freshness wording:** An authenticated production owner asked,
  “When did we last check the backups?” and the live Hermes route responded,
  “I found Backup Check. Shall I run it now?” No confirmation was sent and no
  check ran. The routing defect is now mitigated in the active production-derived
  Hermes overlay: requester-visible Phase 2 backup status is read before action
  parsing, the pinned Hermes 0.21.2 service restarted healthy, and the overlay
  SHA-256 is recorded in the private campaign state. The previous active
  overlay is protected in a mode-0600 rollback snapshot. The exact wording now
  passes disposable authenticated Open WebUI acceptance against this composed
  artifact with synthetic backup state; the answer is canonical, read-only,
  persists in chat, and makes no model call or lifecycle change. Hermes
  auxiliary title/tag prompts also bypass user-action routing, so they do not
  repeat the freshness lookup. The production question was not replayed and no
  lifecycle row was inspected; any old pending confirmation has expired by its
  bounded TTL. This mitigates routing behavior without claiming production UI
  acceptance or determining whether any historical backend write occurred.
  Cross-chat action confirmation/cancellation remains covered by the separate
  disposable browser contract.

- **Deterministic automation:** Owner Away standing policy authorizes four
  read-only templates (Server Health Watch, Low Inventory Summary, Weekly
  Household Summary, and Backup Verification). A HADES-owned isolated run
  ledger and fixed-source runner now pass synthetic checks for pre-read
  authority revalidation, idempotency/concurrent delivery, unknown outcomes,
  failure redaction, and result isolation after revocation. The repository
  Epsilon endpoint now integrates the signed handler, and a packager installs
  its shared modules into an existing generated runtime; endpoint and package
  closure tests pass locally. The runner now requires a live LLDAP resolver;
  strict-readonly membership, immediate group revocation, and deleted-user
  denial pass against the pinned LLDAP runtime. A packaged Epsilon service
  also passes signed execution, isolated state access, service restart/replay,
  and live group revocation under a transient `systemd` unit with
  `ProtectSystem=strict`, `ProtectHome=read-only`, `NoNewPrivileges`,
  `PrivateTmp`, a 128 MiB memory limit, and only the private state directory
  writable. This passed on a pristine Fedora 44 Cloud guest with SELinux
  enforcing, including again after guest reboot and Docker recovery.
  A separately keyed optional result-query endpoint is now covered at the
  source HTTP boundary: owner/shared result reads recheck current authority,
  revoked sharing removes the row from recent results, deleted requesters are
  denied, and the n8n execution key cannot sign a result request. A synthetic
  Hermes 0.21.2 runtime contract proves its signed client and natural-language
  route use the authenticated session subject, return bounded private summaries,
  and make zero model calls. A signed due-list endpoint now selects a bounded
  current-interval batch; synthetic due-to-run HTTP tests prove stable keys,
  replay idempotency, and UNKNOWN suppression. An inactive fixed n8n dispatcher
  artifact uses the built-in Crypto credential. The joined packaged Epsilon +
  pinned n8n/LLDAP + Hermes + authenticated Open WebUI result path passes on a
  fresh SELinux-enforcing Fedora 44 guest, including live grant revocation and
  a full harness rerun after guest-agent reboot.
  **Live production reinspection on 2026-09-26 corrected the earlier staging
  claim:** the generated Epsilon package and protected Phase 3 inputs are now
  present. Its 15-file package manifest matches the installed package, the
  Epsilon and Hermes units are active with the shared state group, and the
  state database is group-shared. The signed HADES result-query endpoint is
  configured. However, production n8n has no Phase 3 workflow and no stored
  credential, so there is still no dispatcher or user-reachable result path;
  no Phase 3 source run or schedule was observed. The broader provenance
  record is materially stale: installed Hermes overlay and version-manifest
  hashes no longer match; its TaskStore hash differs from the generated
  checkout; and its recorded HADES/infra commits are absent from the inspected
  production checkout object stores. The recorded overlay hash is stale. The
  exact active overlay bytes were recovered from preserved local review bundles
  (SHA-256 `782709…`), but are not canonical tracked source; the tested
  `a2ec174…` candidate is not deployed. The installed TaskStore and Epsilon
  package match newer source content. The recorded manifest digest does match the generated reconstruction
  manifest. Reconcile this mixed component source map before refreshing
  provenance or further canary wiring. Backup
  verification through the existing
  read-only Epsilon endpoints returned HEALTHY for both repository bundles.
  Fixed graphs still call Epsilon source URLs directly. The resolver checks
  LLDAP user existence and groups; it does not consume Open WebUI-only role
  changes. Separately, a disposable pinned Open WebUI runtime now confirms
  that changing a user's role to `pending` rejects an already-issued token at
  both the verified-user route and chat-completion boundary. This blocks
  interactive chat before HADES routing, but it is not a revocation source for
  scheduled Phase 3 authority or recipients; continue to use LLDAP
  deprovisioning for those paths. The synthetic
  suite now also passes expired-lease UNKNOWN suppression, failure redaction,
  ten concurrent maximum-quota requests with idempotent replay, and rollback
  after a due item has been observed. The joined runtime acceptance passes on
  two independent pristine Fedora 44 guests with SELinux enforcing, including
  post-reboot replay on the second guest. Keep schedules inactive until
  provenance is reconciled, the fixed dispatcher credential/workflow are
  installed under the rollback runbook, and the remaining production canary
  checks pass.
  A disposable authenticated Beta UI acceptance now confirms approved Low
  Inventory and Groceries-only Weekly Household summaries can each be reviewed
  and created as staged drafts after explicit confirmation; inventory is
  described in household language without internal IDs, duplicate creation is
  rejected without claiming an unscheduled draft is running, and a request to
  run the unconnected draft clearly says it was not run. The staged Phase 3
  database remains byte-for-byte unchanged across that run request and across a
  bare “Yes” in another chat; the original chat can still confirm its own
  pending draft. It records one create audit per draft and zero manual runs,
  and the UI turns persist in chat history. Beta can explicitly share the Low
  Inventory draft with Gamma; Gamma sees it as shared, then loses visibility
  immediately after Beta revokes the share.
  This caught and repaired a route-ordering defect where the legacy Phase 2
  inventory handler incorrectly blocked household draft creation. This is
  source-only synthetic evidence; it does not close production wiring or owner
  acceptance.
  Keep schedules disabled until then. This is an implementation gate, not a
  request for another product authorization.

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
  disposable authenticated Alpha/Beta browser acceptance now proves the
  owner-only action is hidden from Beta, an authenticated direct Beta preview
  still fails closed, and Alpha can review, explicitly apply, and receive
  canonical Grocy read-back. Beta caused zero OCR or Grocy calls. The
  injected-route regression also proves an unmapped admin is denied before
  request parsing. A disposable CPU PaddleOCR probe on a low-contrast, rotated
  synthetic multi-column receipt found that readable price/name fragments can
  arrive split and out of order; the preview route now groups PaddleOCR boxes
  into visual rows before review. The authenticated browser regression covers
  that fragment ordering and remains review-only until explicit confirmation.
  Broader receipt-layout coverage, especially photographed household receipts,
  remains staged work; no production receipt was used.
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
- **P1: public/private release boundary remains open:** the current private
  local `main` snapshot and its unpublished commit range fail the redacted
  private-topology audit; do not publish that branch or rewrite public
  history. The fetched public snapshot also has a synthetic test-fixture match
  in the current-tree guard, and its reachable history retains earlier
  redacted findings. A clean-base forward-guard branch is pushed on
  `codex/public-safety-range-guard-20260927`; current-tree, browser-policy,
  redaction, and introduced-range checks pass locally. A follow-up regression
  found and fixed a path-audit blind spot where a newly introduced
  credential-like filename could reuse a base blob; cleanup-only removal of a
  legacy path remains allowed. Hosted CI passes at `1554f94`. PR creation
  through the connected GitHub integration again returned 403 (`Resource not
  accessible by integration`); no PR has been opened, no alternate write
  route was attempted, and no deployed runtime was changed.
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
  **Token-scope correction (2026-09-27):** Read-only inspection found the
  privilege-separated Alexandra/Erebus tokens had no token-specific ACL even
  though their backing service user has `PVEAuditor` at `/`. Restored only the
  existing read-only Proxmox contract: added `HADESNodeAudit` (`Sys.Audit`) to
  each token at `/`, and `HADESVmAudit` (`VM.Audit`) only at `/vms/803` for
  Alexandra's CT 803 and `/vms/802` for Erebus' HADES VM 802. No user ACL or
  write privilege changed. `pveum user token permissions` now shows those
  scopes. Using the active protected token inputs, `/cluster/resources`
  returns HTTP 200 with exactly a node plus the approved guest from each PVE
  instance; historical VMs 800/801 and other Erebus guests are not returned.
  The rows include current CPU, memory, disk allocation, network counters, and
  uptime. `VM.GuestAgent.Audit` was not granted; VM 802 `get-osinfo` and
  `get-fsinfo` had returned HTTP 403 before this scoped correction and remain
  outside the enabled adapter contract. No host/VM workload state changed.
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

- **Production server-status misroute and false memory-write claim (mitigated; historical effect unknown):** On 2026-09-25, one authenticated owner question, “Is everything okay with the servers?”, returned a model-generated answer claiming a persistent personal-memory update instead of server health. Read-only chat history confirmed the answer belonged to that question and showed no recorded tool call; whether Hindsight stored anything remains unverified. A regression run against the exact active production-derived Hermes overlay reproduced a task-confirmation misroute when a synthetic pending approval was present. The overlay was repaired with the already-committed plural server/computer route and standalone Task-confirmation guards, then Hermes was restarted. The exact question now passes against that repaired artifact with a deterministic read-only adapter, zero model calls, and an unchanged synthetic approval; the production Hermes health endpoint returned HTTP 200 after restart. The production question was not repeated, no memory row or queue item was inspected, and no cleanup/replay was attempted. Treat the routing defect as mitigated; retain the possible historical memory side effect as unknown.

- **Fresh-session briefing continuity:** A disposable authenticated Alpha UI now receives a morning briefing, then opens a separate authenticated browser context and asks what the briefing found and what needs attention. The new turn refreshes the synthetic live Proxmox source and Alpha's current Task state, says it refreshed rather than relying on stale conversation, persists in the new chat, and makes no model call (the synthetic endpoint is deliberately unavailable). The full Alpha/Beta/Gamma UI harness also preserves each existing AWAITING_APPROVAL/BLOCKED/FAILED Task state while checking attention and media-device clarification. This test uses an isolated synthetic homelab adapter, a temporary automation database, an unavailable loopback Grocy endpoint, and an empty finance path; it is not production acceptance. The blocker query exposed an empty-availability edge in the detailed homelab summary, now fixed and covered by the Hermes wrapper regression. Report: `/tmp/hades-task-attention-3160196.json` (mode 0600). No production query or change was made.

- **Hindsight route latency baseline:** The disposable pinned Hindsight + Hermes 0.21.2 runtime test now distinguishes a genuinely lexical-unmatched paraphrase from a recent-list hit and instruments the `HindsightClient.recall` path. Ten in-process samples after two warmups measured direct tagged-memory matching at p50 4.4 ms / nearest-rank p95 4.8 ms (zero semantic calls) and the Hindsight recall fallback at p50 252.4 ms / p95 271.1 ms (one recall call per sample). A synthetic explicit retain followed by a natural recall in a fresh Hermes Python process completed in 1,997 ms combined, including interpreter startup twice. Report: `/tmp/hades-hindsight-latency-20260925.json` (0600). This is a local, synthetic baseline only: it does not establish production latency, backlog recovery, or an Hindsight SLO. The production 33.1-second fresh-recall smoke remains a single observation; no production memory or queue detail was read or changed.

The bounded route benchmark was repeated in two additional fresh Hindsight
containers and volumes; all three independent runs met the candidate limits
(100 ms direct p95, 1,000 ms Hindsight fallback p95, and 4,000 ms for the
single retain→fresh-process recall). Run 2 measured 3.0/261.4 ms and 1,996 ms;
run 3 measured 4.5/253.0 ms and 2,001 ms. The optional benchmark mode now
asserts these limits. Reports are `/tmp/hades-hindsight-latency-20260925-run2.json`
and `...-run3.json` (0600). This establishes repeatability only for the pinned
synthetic local setup. Do not promote these to a production SLO or infer that
the production Hindsight backlog is healthy.

- **Open WebUI interrupted-request honesty:** The pinned 0.11.1 HADES theme now
  reports that a disconnected request may have completed and tells the user to
  check the chat before retrying; it no longer claims that nothing changed or
  exposes a raw browser `Failed to fetch` message. A synthetic authenticated
  browser run forced the first chat request to fail, verified the composer
  recovered, and completed a new chat against a local deterministic responder.
  Source contract and browser acceptance passed against a disposable image
  built from the pinned base. This is not a production deployment or acceptance
  claim.

- **Owner finance month comparison:** The read-only local CSV route now answers
  “Why was spending higher this month?” by comparing month-to-date expenses
  against the same calendar days of the prior month and showing the largest
  statement category/description increases. It explicitly says those amounts
  do not establish a cause, includes pending rows, and refuses a current-month
  conclusion when the export is stale or lacks prior-period expense rows.
  Synthetic CSV, statement-window, and household-denial contracts pass. A
  disposable authenticated Alpha/Beta Open WebUI + Hermes run now also passes
  with synthetic current/prior-month rows: Alpha receives same-calendar-day
  expense totals and category changes with income excluded, while Beta is
  denied before inference. The deliberately unavailable model endpoint
  verifies the deterministic route; chat persistence passes and both the
  TaskStore and CSV fixture hashes remain unchanged. No real finance file or
  production service was read or changed; owner Actual Budget credentials and
  production/live-ledger acceptance remain separately gated.

**Hindsight aggregate refresh — 2026-09-27:** A read-only query against all
13 banks again reports 3 pending / 470 failed operations and 52 pending /
1,118 failed consolidations, unchanged from 2026-09-26. API health and version
are HTTP 200 / 0.9.2; the pinned image is unchanged, the container is running
with zero restarts, and `HINDSIGHT_API_WORKER_ID` remains unset. No bank names,
memory rows, or operation rows were retained; no retry, replay, deletion,
restart, or configuration change occurred. Unknown operation ownership still
prevents safe recovery.

**Latest aggregate-only refresh — 2026-09-27 20:05 UTC:** The API remains
healthy (HTTP 200, database connected) on version 0.9.2 and the same pinned
image, with zero container restarts and no configured stable worker ID. All 13
banks answered their `/stats` reads. Totals are 3 pending / 470 failed
operations and 54 pending / 1,118 failed consolidations; one bank has pending
consolidations, but its identity was not retained. Pending consolidations rose
by two from the prior 52-count sample. No bank identifiers, memory rows, or
operation rows were retained; no retry, replay, deletion, restart, or
configuration change occurred. This does not identify the backlog cause or
make recovery safe; worker ownership remains unknown.


**Receipt duplicate-apply hardening (source / synthetic verified, not production-deployed):** The owner-scoped Open WebUI apply route now serializes receipt fingerprint check, `SUBMITTED` marker, Grocy writes, canonical read-back, and `APPLIED` marker across worker processes. The bounded JSON ledger must be a regular mode-0600 file under 512 KiB with at most 4,096 valid entries; unsafe lock/ledger state and full capacity fail closed before writes. Its file and containing directory are synced before the Grocy mutation. Eight independent worker processes concurrently confirming one receipt produced exactly one canonical stock write; unsafe permissions and full capacity produced no write (`scripts/test-receipt-ocr-concurrent-apply.py`). Production acceptance remains separately gated.

- **Overlay source-map refinement (2026-09-26):** Read-only history queries
  across the production HADES checkout and eight reconciled clones show that
  the active `_hades_prefetch` and `_hades_run_conversation` bodies originate
  in tracked commit `77a78170bb70550b9c4d27764bf11ff488c3586d`, although neither
  whole active body exactly matches a tracked revision. The active conversation
  route is 95.5% line-similar to current HEAD, but it retains actor-wide
  `pending_for_actor` confirmation recovery and omits the API server-chat ID
  from confirmation identity; current source rejects that fallback. The
  existing static isolation test cannot run against the old active helper
  signature (it exits with `TypeError` before its assertions), so this is not
  new runtime proof. Treat the discrepancy as an open source-level cross-chat
  authority risk; keep production read-only until the active deltas are
  reconciled and the exact artifact is tested with the pinned Hermes runtime.

- **Recipe schema leakage in pre-hotfix overlay (mitigated; live acceptance
  remains open):** The previous overlay `7827093c…` was exercised under pinned
  Hermes 0.21.2 with synthetic owner/household identities and a synthetic MCP
  schema catalog. Both model requests received all 12 fixture tools; the
  household catalog included nine owner-only recipe operations, including the
  registered `recipe-url-ingest` preview/apply/paste family and recipe
  authoring/serving tools. The separate deferred generic-create discovery and
  tool-call assertions passed; other deferred owner-only operations were not
  covered. The same catalog failure reproduced on undeployed candidate
  `a2ec1740…`. A read-only key-name inspection of production Hermes config shows
  `recipe-url-ingest` is registered, but the live authenticated household
  catalog was not queried, so actual production exposure is not claimed. The
  exact synthetic report is `/tmp/hades-active-recipe-scope-20260926.json`
  (0600). The replacement overlay `40f37c7b…` now includes eager/deferred
  catalog filtering and the direct executor boundary. Those paths pass
  registered synthetic tests on pinned Hermes 0.21.2. No authenticated
  production household catalog was queried; treat live acceptance as open.

- **P1: owner-only recipe tool scope hotfix deployed; authenticated live
  acceptance remains open:** The exact
  active overlay SHA `7827093c…` was loaded under Hermes 0.21.2. With a local
  synthetic registered tool fixture, a household direct `recipe_create` call
  and `recipe_url_apply` call received no parser scope block and reached the
  synthetic handler; an owner raw serving call also reached its fixture
  handler. No production MCP or user data was touched. A read-only inspection
  of the active Hermes config confirms the `recipe-url-ingest` server is
  registered, so this was a production deployment risk; an authenticated live
  household call was not made and no actual user impact is claimed. The scoped
  candidate SHA-256 `40f37c7b…` is now installed on VM 802 as the active overlay,
  atomically, with original bytes preserved in a root-only rollback backup.
  Hermes restarted and is active; `/health` returns 200/`ok` on the configured
  bridge listener. Synthetic pinned-runtime eager/deferred/direct executor
  tests pass. Do not treat this as authenticated household acceptance: that
  remains untested, and the provenance endpoint still needs refresh.

  **Read-only refresh (2026-09-27):** VM 802 reports `hades-hermes.service`
  active/running with zero restarts; `/health` reports Hermes 0.21.2. The active
  overlay at `$HADES_HOME/generated-full/config/overlay/sitecustomize.py` is
  SHA-256 `40f37c7be0c12e0df552148a8d5cab098f26ef8ecb7b767c39a14621fed55759`,
  owned `root:hades-runtime` mode 0644. The deployed checkout remains detached
  at `b102dfdf42fc564c040c432cb2c6e87ee1f27d22` with 18 dirty paths. This
  confirms the running artifact and health only; it does not close source
  provenance or authenticated household catalog acceptance.

  The current worktree now applies `_hades_filter_tools_for_scope` and the
  per-turn tool allowlist at Hermes' shared direct-call parse boundary. The
  strengthened `scripts/test-grocy-tool-scope-hermes-runtime.sh` registers
  actual synthetic tools in Hermes' registry (the prior test's deferred creator
  fixture was unregistered and its denial assertion was vacuous). It passes:
  registered owner discovery is visible only to the owner, household deferred
  `tool_call` is denied, forged direct household create/import and owner raw
  serving calls are blocked before the synthetic handler, normal household
  reads and owner recipe creation remain available, and an invalid HADES
  subject fails closed. Report: `/tmp/hades-active-recipe-scope-20260926.json`
  (0600). Source and test edits are uncommitted in the existing dirty worktree.
  Exact rollback is at
  `$HADES_HOME/generated-full/backups/scope-hotfix-20260927T0019Z/`; the
  original SHA-256 is `7827093c…`. Next: perform read-only post-deploy
  provenance and scope/config reconciliation; no authenticated production
  recipe invocation has been made.

**Hindsight aggregate-only refresh — 2026-09-27 22:33 UTC:** All 13 bank
`/stats` reads succeeded. Totals remain 3 pending / 470 failed operations and
54 pending / 1,118 failed consolidations, unchanged from the 20:05 UTC sample.
Hindsight health/version remain HTTP 200 / 0.9.2 on the manifest-pinned image
digest; the container is running with zero restarts, one persistent mount, and
no configured `HINDSIGHT_API_WORKER_ID`. Bank identifiers were used in memory
to issue the per-bank aggregate queries but were not printed or retained. No
memory rows or operation rows were queried; no retry, replay, deletion, restart,
or configuration change occurred. Stable aggregate counts do not identify
backlog cause or operation ownership, so recovery remains unsafe.

**Hindsight aggregate-only refresh — 2026-09-28 14:48 UTC:** A temporary
strict-host-key SSH tunnel to the documented loopback API allowed the local
aggregate-only helper to read all 13 banks' `/stats` endpoints. Totals are 3
pending / 470 failed operations and 57 pending / 1,118 failed consolidations;
the pending consolidation count increased by three from the 2026-09-27 22:33
snapshot. The API reports healthy/database-connected; `/version` reports
0.9.2. The pinned container digest remains
`sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`,
with zero restarts. A narrow environment-name check confirms
`HINDSIGHT_API_WORKER_ID` remains unset. The disposable pinned-image worker
recreation contract still passes. No production identifiers, operation rows,
or memory rows were retained or queried; no retry, replay, deletion, restart,
configuration change, or memory action occurred. Unknown worker ownership
still makes production backlog recovery unsafe.


**Hindsight aggregate-only refresh — 2026-09-29:** All 13 production banks
answered the documented `/stats` reads: 3 pending / 470 failed operations and
57 pending / 1,118 failed consolidations, unchanged from 2026-09-28. The pinned
image remains `sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`,
container running with zero restarts; `/health` is healthy/database connected,
API version is 0.9.2, and listener remains loopback-only. The stable worker ID
remains absent. This is aggregate-only evidence: no identifiers or row details
were retained or inspected, and no retry, replay, deletion, restart, memory
action, or configuration change occurred. Unknown worker ownership still makes
backlog recovery unsafe.

- **Hermes selected-profile correction — 2026-09-29:** The prior check read
  `$HADES_HOME/generated-full/profile/config.yaml`, but the running service
  starts with `-p hades`. Its selected profile is
  `$HADES_HOME/generated-full/profile/profiles/hades/config.yaml` (SHA
  `31108a8a…`), with nine registrations on a fresh structural parse. All four V1-required servers,
  `recipe-url-ingest` included, are registered. `finance-file-import` and `receipt-ocr-gateway` are the two owner-gated
  registrations. Three staged
  servers (`hades-agent-zero`, `homelab-control`, `public-page-extract`) are
  also registered. A source-history trace recovered all seven configured
  Python server blobs in current local HADES history: five match current HEAD,
  while recipe authoring and read-only homelab map to earlier tracked commits.
  Activation intent is not recorded and no gated server was invoked; treat
  activation as OWNER-DECISION-UNVERIFIED, not proof of an authorization
  violation. The top-level four-entry profile observation is superseded; the earlier
  nine-registration count is confirmed. A command-only source scan had omitted
  the HTTP-form receipt registration. Grocy resolves to the user-local
  0.2.0 executable without canonical lock provenance. The canonical profile checker now requires owner-gated
  entries disabled in the shipped template and warns on their presence in an
  enabled operator profile. This refresh was read-only; no production profile
  or service changed.

### Owner continuation transcript follow-up — 2026-09-29

The newly supplied live exchange confirms that the first turn also omitted the
plan details and explicit confirmation action it promised; “Perfect, continue”
then received a generic greeting. The tracked Hermes continuation contract
passes the matching transcript, but the active production overlay lacks that
helper and remains a mixed-provenance no-deploy artifact. No VM/server/IP/
firewall action occurred. See [self-service-gamma.md](self-service-gamma.md)
for evidence and current readiness limits.

- **Minecraft request-plus-endpoint dogfood — 2026-09-29:** the exact phrase
  “spin up … and give me the port/IP” was incorrectly consumed by the
  read-only endpoint inventory route, and the authenticated harness encoded
  that bad expectation. Tracked source now gives explicit provisioning intent
  precedence while keeping endpoint-only questions read-only. The exact prompt
  passes the disposable authenticated A→B→A plan/continuation/explicit-create
  flow and only uses the loopback Proxmox fixture. Production remains unresolved:
  active overlay is mixed `d827e9db…`, no Minecraft template is configured, and
  no live server/IP/firewall action occurred. See `docs/self-service-gamma.md`.


### Active-overlay dogfood replay — 2026-09-29

A fresh strict-host-key, read-only VM 802 check confirmed `hades-hermes.service`
is active (PID `2021647`, zero restarts) and `/health` reports Hermes `0.21.2`.
The selected overlay remains SHA-256
`d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`; it
does not define the tracked transcript-plan helper. The provenance endpoint at
`<PRIVATE_LAN_ADDRESS>:8643/v1/epsilon/provenance` still reports generation time
`2026-09-24T07:54:33Z` and overlay `1863ed16573b7c040b78de98e7a3e6ad4463efb167c55c3b2c92bdc4d0a3c12a`, not the active bytes.

A mode-0600 local copy of the exact active overlay was exercised under pinned
Hermes `0.21.2` with synthetic state and the supplied conversation. It returned
the plan promise with `api_calls=0`, then routed “Perfect, continue” to the
unreachable synthetic model endpoint (`api_calls=1`) and exhausted its retries.
The user-reported generic greeting is therefore consistent with the exact active
artifact failing to recover/fail closed; the synthetic replay itself only proves
that inference was attempted, not the exact greeting text. The current tracked
source's focused continuation contract passes this sequence with zero model or
infrastructure calls. No live chat was replayed, and no production file,
service, VM, Minecraft workload, or firewall was changed.


- **VM 802 runtime composition and rollback recheck — 2026-09-29:** Confirmed the
  selected-profile count is nine: four V1-required, two owner-gated, and three
  staged registrations. Several configured source files differ from
  checkout HEAD or are absent there; registrations span two dirty checkouts,
  and Grocy uses a user-local venv without canonical manifest evidence. The
  exact protected code/config rollback archive still matches all but one
  generated `.pyc` cache entry. This confirms rollback availability while the
  manifest-bound runtime composition and update procedure remain unresolved.
  No registered owner-gated or staged MCP was invoked and no production state
  changed. A clean clone of HADES `32e146a` passes profile classification,
  manifest closure, synthetic install/validator/non-mutating doctor, Minecraft
  continuation, cross-chat confirmation, and public-research collector/MCP
  contracts. These qualify current
  source/default profile only, not the live historical source/private profile.
  See `docs/hermes-overlay-inventory.md` for the source/path matrix.
