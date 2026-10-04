# HADES LIVE-STATE ADVISOR HANDOFF

**Timestamp:** 2026-09-23 (America/Chicago; evidence captured during this session)

**Evidence boundary:** This is a fresh live-state handoff, not a transcription of prior status files. Live checks were made against HADES guest (`<PRIVATE_LAN_ADDRESS>`), the owner-facing HADES URL, the three configured authenticated identities, the reachable inference nodes, local Git repositories, and the local deployment artifacts. Secrets, tokens, passwords, private memory, and private financial data are intentionally omitted. Where a claim comes from an older document or an unrepeatable fixture, it is labelled `HISTORICAL EVIDENCE`; it is not treated as live proof.

## Current handoff delta

The report below was captured before the final Alpha substrate work. The following later evidence supersedes conflicting older lines:

- HADES source code at this evidence capture is `72a5dc0` on `main`; the following handoff-only commit does not alter deployed code — `REPOSITORY VERIFIED`.
- The deployed runtime is HADES `72a5dc0` / infra `bf648f5`, with machine-readable provenance and the live Hermes/Open WebUI stack verified — `LIVE VERIFIED` for the deployed artifact.
- Durable Task substrate, canonical Grocy read/ledger path, bounded typed n8n wait, fresh Hindsight recall, and composed homelab partial-source handling are `LIVE VERIFIED` from the resumed Alpha run. The targeted homelab adapter, capability boundary, Task store, liveness, and Python syntax checks are freshly green — `REPOSITORY VERIFIED`.
- A combined authenticated mobile soak at `390x844` passed: Owner abandoned a turn; Owner’s reloaded second tab recovered; Household A completed a shared pantry read; Household B received a server-side Agent Zero denial. This is `LIVE VERIFIED` for those cases. It does not prove desktop, 320x568, n8n outage, or all revocation cases.
- The same bounded soak subsequently passed at `320x568` and `1440x900`, covering the same abandonment, stale-tab recovery, household read, and Agent Zero-denial cases — `LIVE VERIFIED` for those viewport cases.
- The previously reported stale mobile failures were traced to the harness selecting a hidden/incorrect New Chat or submit control; the harness now targets `#new-chat-button` and the real composer path. That diagnosis is `REPOSITORY VERIFIED` plus the passing DOM run, not a claim that every stale-tab path is closed.
- The resumed health-watch audit found and corrected three live-path defects: semantic duplicate-watch admission, stale create-preview precedence over current share/revoke actions, and Phase 3 metadata interception of health-watch sharing. The deployed HADES code is `LIVE VERIFIED` at these fixes; canonical state is currently one legitimate 15-minute watch, with stale test watches backed up and their n8n workflows inactive.
- A fresh authenticated DOM proof using explicit confirmed owner prompts then passed sharing and revocation: Household A saw the 15-minute HADES Core Watch while shared, then saw `You are not monitoring any authorized servers yet.` after revoke; canonical SQLite read-back showed one watch with empty sharing and no pending previews — `LIVE VERIFIED`. The two-turn bare-`yes` harness path can still replay a stale create draft, but semantic uniqueness prevents duplicate canonical watches; that harness behavior remains `UNVERIFIED`.
- Targeted web, voice STT/TTS, homelab partial-source, Task, liveness, and typed n8n failure contracts are `REPOSITORY VERIFIED`. A fresh live dependency-outage injection was not performed because stopping production dependencies is outside the authorized mutation boundary; live outage behavior therefore remains `UNVERIFIED`, not `PASS`.
- A bounded authenticated owner DOM transport fixture aborted one chat-completion request, produced visible `Failed to fetch` with no stale Stop state, and then recovered on a fresh `hello recovery` turn — `LIVE VERIFIED` for transport failure/re-entry. It does not claim a live SearXNG, Grocy, n8n, or inference-service outage.
- A fresh Hindsight retain/recall proof eventually passed in a genuinely new conversation for marker `alpha-memory-marker-1790217562` — `LIVE VERIFIED`; the retain worker was heavily backlogged and recall required a delayed retry, so memory correctness is green but freshness/latency is an active product concern.

## 1. Executive state

HADES is currently a local-first owner/household assistant running on HADES Core HADES guest. The owner-facing Open WebUI and Hermes gateway are live; the core containers for Hindsight, Grocy, SearXNG, Agent Zero, LLDAP, OCR, and n8n are running. The current product is useful for authenticated owner chat, household-scoped Grocy reads, bounded read-only HADES health/backup workflows, web/search surfaces, and selected owner-only tools.

- **Core owner chat:** `LIVE VERIFIED` — Open WebUI is reachable and authenticated DOM prompts returned live responses.
- **Phase 2 bounded read-only automation:** `LIVE VERIFIED` for the already accepted owner/household surfaces; n8n is running on loopback, but arbitrary workflow creation and external notifications remain outside authority.
- **Phase 3 household self-service:** `REPOSITORY VERIFIED` and `SYNTHETIC VERIFIED` only. The approved typed catalog, ownership, quotas, sharing, revocation, and admin contracts pass local tests. A staged household UI gate is deployed, but it does not create n8n workflows or grant unrestricted production creation.
- **Main product defect found in this audit:** `BROKEN` — the owner UI showed one normal 15-minute Core Watch plus two stale/unknown 10-minute health-watch entries. This is state hygiene/product clarity, not evidence that authorization was broadened.
- **External recovery:** `EXTERNAL-GATED` — storage host is reachable at its management ports, but the available noninteractive SSH identity was not accepted; fresh ZFS/backup custody could not be independently re-read from that host.
- **Overall:** `DAILY USABLE` for the owner’s bounded assistant workflows; `DOGFOOD USABLE` for household read-only sharing; `STAGED` for typed household automation; not yet a general autonomous household operator.

**Post-audit correction:** During resumed Phase 3 acceptance, an authority projection bug was found and fixed: the Phase 2 default health resource had been implicitly granted to every household account. The deployed code now uses only explicit subject/resource grants. Fresh DOM evidence after restart shows Household B sees only Low Grocery and a Groceries-only Weekly Summary, and a server-watch request is denied without creating state — `LIVE VERIFIED` after correction. A low-inventory share/run/revoke cycle also completed through the DOM; staged records were cleared afterward.

## 2. Source/deployment revisions

### HADES repository

- Branch: `main` — `REPOSITORY VERIFIED`.
- HEAD: `e609fec` (`Close Epsilon Phase 2 dogfood acceptance`) — `REPOSITORY VERIFIED`.
- Working tree: dirty with the current Phase 3 implementation: modified `hermes/sitecustomize.py`; new `integrations/automation/phase3_self_service.py`, `scripts/test-phase3-self-service.sh`, and `deploy/hades-hermes-phase3-staged.conf` — `REPOSITORY VERIFIED`.
- Public tracking: `origin/main` exists and local `main` is ahead by 542 commits (`0 542` in upstream-left/right count) — `REPOSITORY VERIFIED`. This means public GitHub is not a representation of current local source truth.
- Recent meaningful commits include `e609fec`, `49b8b6a`, `3c7c4df`, `4b12040`, `4d79dd6`, `9465179`, `c97217f`, `9ae43ef`, `ca6c1ff`, and `e74e786`, dated 2026-09-22/23 — `REPOSITORY VERIFIED`.
- Relevant tags present: `decision-plane-alpha-baseline`, `gamma-adversarial-dogfood`, `gamma-adversarial-preflight`, `daily-driver-reliability-beta` — `REPOSITORY VERIFIED`.

### Infrastructure repository

- Branch: `main`; HEAD `bf648f5` (`Record Epsilon canary lifecycle acceptance`) — `REPOSITORY VERIFIED`.
- Working tree is clean — `REPOSITORY VERIFIED`.
- No remote tracking branch is configured in this checkout; public-repository parity is therefore `UNVERIFIED`.
- Recent commits include `fa875c4`, `6eb2cc8`, `f064783`, `6697393`, `9d1a435`, `e42f0fb`, `413bc20`, `aa81717`, and `5f26762` — `REPOSITORY VERIFIED`.

### Deployed revision

`DEPLOYED REVISION: LIVE VERIFIED.` The live Hermes unit runs from `$HADES_HOME/Hades-reconciled-b102dfd` with an overlay at `$HADES_HOME/generated-full/config/overlay`. The live provenance record at `<PRIVATE_LAN_ADDRESS>:8643/v1/epsilon/provenance` reported HADES code `72a5dc0`, infra `bf648f52f5ab0e4da9ebd811f9ccc6866cf5341a`, Hermes `0.21.2`, overlay hash `d67df...`, and manifest hash `811807...`. Subsequent local commits are report/test changes unless explicitly deployed; the later task-lifecycle runtime deployment is recorded in the Alpha report below.

## Alpha continuation delta — 2026-09-24

The durable Task owner surface was extended and deployed with revision-bound approval, owner-requested continuation, canonical Grocy read completion, and completed/cancelled task inspection from a fresh conversation. Live evidence: the authenticated DOM path created the spaghetti task, crossed `WAITING → AWAITING_APPROVAL → READY → RUNNING → COMPLETED`, and returned a fresh-session completed status. Canonical SQLite read-back for task `task-aa301d26585136f0f098` was `COMPLETED`, revision `12`, with events `CREATED`, `PLAN_ACCEPTED`, `EXECUTION_STARTED`, `EXECUTION_RESULT`, `WAIT_REQUESTED`, `N8N_WAIT_SCHEDULED`, `APPROVAL_REQUESTED`, `APPROVED`, `EXECUTION_STARTED`, `EXECUTION_RESULT`; no active synthetic task rows remained. This is `LIVE VERIFIED`. Replan/cancel remains covered by the earlier six-turn DOM fixture; ambiguous bare `yes` and bare `resume` are intentionally not treated as task authorization because they collide with broader memory/Health Watch routes.

## 3. Live topology

The following addresses are current inventory references plus fresh reachability checks. Host role details not directly re-read are labelled accordingly.

| Node | Address / identity | Current evidence and role |
|---|---|---|
| hypervisor host / Proxmox | `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` reachable by ICMP; Proxmox API URL is configured in the live Hermes unit as `https://<PRIVATE_LAN_ADDRESS>:8006/api2/json`; direct node state was not privileged-read in this audit. Role: virtualization host, `UNVERIFIED` beyond reachability/configuration. |
| HADES Core / HADES guest | `<PRIVATE_LAN_ADDRESS>`, hostname `hades-core` | `LIVE VERIFIED`; SSH, Open WebUI, Hermes, and all listed core containers active. |
| Agent Zero / configured guest | no fresh IP established | `UNVERIFIED` as a separate VM. The current deployed Agent Zero runtime is a container on HADES guest, `hades-agent-zero`, loopback-published at `127.0.0.1:7002`. |
| storage host | `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` at TCP/22 and TCP/8006; noninteractive SSH identity not accepted, so current ZFS state is `EXTERNAL-GATED`. It must not be called offsite. |
| storage host service guest / 803 | `<PRIVATE_LAN_ADDRESS>` | `HISTORICAL EVIDENCE` from inventory; not independently re-probed in this bounded audit. |
| deep inference provider | `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama HTTP on `:11437`; role Deep inference. |
| specialized inference provider | `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama HTTP on `:11434`; role specialized/code inference. |
| fast inference provider | `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama HTTP on `:11435` and voice HTTP on `:8766`; role fast inference and voice. This is distinct from Hermes Agent. |
| management host | `<PRIVATE_LAN_ADDRESS>` | `HISTORICAL EVIDENCE` inventory role and address; not independently re-probed here. |

Generic host health is not being represented as application acceptance. In particular, reachable ICMP or an open port does not prove GPU, Proxmox, ZFS, or workload readiness.

## 4. Core services

Fresh HADES guest evidence shows:

| Capability | Service/path | Boundary and state |
|---|---|---|
| Owner UI | `hades-open-webui`, `<PRIVATE_LAN_ADDRESS>:3000 -> 8080`, image/container `58c3ea6213a9` | `LIVE VERIFIED`; authenticated owner-facing DOM. Household access is policy-scoped. |
| Hermes Agent | `hades-hermes.service`, Hermes `0.21.2`, working directory `Hades-reconciled-b102dfd` | `LIVE VERIFIED`; gateway active. It is the policy/tool boundary, not a claim of unrestricted capability. |
| Hindsight | container `84ab276b8f50`, loopback `:8888/:9999` | `LIVE VERIFIED`; `/health` returned `status=healthy`, database connected. |
| Grocy | `hades-grocy`, loopback `:7003` | `LIVE VERIFIED`; HTTP redirect response and owner DOM read path observed. Canonical writes remain explicit-confirmation only. |
| SearXNG | `hades-searxng`, loopback `:8080` | `LIVE VERIFIED`; root HTTP returned 200; Hermes config points to it. |
| LLDAP | `hades-lldap`, loopback `:17170` | `LIVE VERIFIED`; container healthy and HTTP returned 200. LDAP-backed auth smoke succeeded for all three configured users. |
| Agent Zero | `hades-agent-zero`, container `680ab243d358`, loopback `:7002` | `LIVE VERIFIED` runtime; `OWNER-GATED` for delegated operator actions. Household delegation is denied by policy. |
| n8n | `hades-n8n-epsilon`, container `9f693fd55655`, loopback `:5678` | `LIVE VERIFIED` and `/healthz` returned `status=ok`; current Phase 3 does not create arbitrary n8n graphs. |
| OCR | `hades-receipt-ocr`, image `hades-receipt-ocr:20260918-r3`, loopback `:8765` | `LIVE VERIFIED` container; UI workflow acceptance is `HISTORICAL EVIDENCE` unless separately re-run. |
| Finance | Hermes policy/tool surface | `OWNER-GATED`; no private financial record was queried or printed in this audit. Household finance remains denied. |
| Home Assistant | no fresh live path established | `DEFERRED` / `OWNER-GATED`; not enabled as a household action surface. |
| Browser research | Open WebUI/Hermes search path | `LIVE VERIFIED` at the web/search boundary from prior fresh owner acceptance; privileged/login-required browser interaction remains `DEFERRED`. |

The live systemd state was `active/running` for `hades-hermes.service` and `hades-epsilon-source.service`. The service environment explicitly shows loopback n8n, SearXNG, HADES state SQLite, Proxmox read/control URL, the staged Phase 3 flag, and the configured household subject/resource mappings; sensitive values were redacted.

## 5. Models/routing

Fresh `/api/tags` and `/v1/models` checks establish the following endpoints. These are backend availability facts; exact Open WebUI route selection for every named display preset is not exposed by the endpoint list alone.

| Route / display | Physical node | Endpoint and model evidence | Execution / capability |
|---|---|---|---|
| Hades Fast | fast inference provider, `<PRIVATE_LAN_ADDRESS>` | `:11435`, `qwen3:8b` | `LIVE VERIFIED`; Ollama exposes completion, tools, thinking. |
| Hades Deep | deep inference provider, `<PRIVATE_LAN_ADDRESS>` | `:11437`, `qwen3.6:35b` plus aliases `hades-fast`, `agent-zero-fast`, smaller models | `LIVE VERIFIED` endpoint/model inventory; actual per-prompt route selection `UNVERIFIED`. |
| Code | specialized inference provider, `<PRIVATE_LAN_ADDRESS>` | `:11434`, `gemma4:e4b` available | `LIVE VERIFIED` model availability; display-preset binding `UNVERIFIED`. |
| Creative / Uncensored Writing / Security Lab | likely specialized inference provider/deep inference provider aliases | Current physical model/preset bindings not proven by the live endpoint inventory | `UNVERIFIED`; do not repeat old intended routing as fact. |
| Embedding | specialized inference provider | `nomic-embed-text:latest` available on `:11434` | `LIVE VERIFIED` availability. Hindsight’s selected embedding path was not re-derived here. |
| Voice STT/TTS | fast inference provider | `<PRIVATE_LAN_ADDRESS>:8766` returned a live HTTP 404 at `/`, proving listener reachability only | `LIVE VERIFIED` listener; exact STT/TTS health and latency `UNVERIFIED`. |

Historical assumptions are therefore only partly current: deep inference provider `qwen3.6:35b` on `:11437`, fast inference provider fast on `:11435`, specialized inference provider specialized endpoint on `:11434`, and fast inference provider voice on `:8766` all remain live. A blanket “64K context” claim and every display-preset binding are `UNVERIFIED` in this handoff.

## 6. Real owner dogfood

The sample below used the real authenticated HADES DOM, not direct MCP calls. Responses are intentionally summarized without private data.

| Owner prompt | Route/tools | Visible result | Canonical check / classification |
|---|---|---|---|
| “say hello and tell me what you are” | HADES chat | Returned a normal assistant greeting | `LIVE VERIFIED`; owner UI path and session were real. |
| “do we have HADES Synthetic Milk?” | Grocy household read | Returned 2 units | `LIVE VERIFIED` and `LIVE VERIFIED` canonical Grocy fixture read. |
| “what is the current status of HADES Core?” | health-watch read | Reported Core Watch up, enabled, every 15 minutes | `LIVE VERIFIED`; duplicate stale entries also appeared in a later list. |
| “what am I monitoring?” | health-watch listing | Returned one normal watch and two unknown 10-minute watches | `BROKEN` product-state hygiene; requires cleanup/reconciliation. |
| “give me a concise read-only homelab status…” | bounded homelab path | Returned the Core Watch status, but did not provide the requested node inventory | `LIVE VERIFIED` path, `BROKEN`/awkward answer composition. |
| “what models can I use?” | model catalog | Not included in the completed sample because the long multi-prompt session exceeded the harness context budget | `UNVERIFIED` for this audit. |
| Agent Zero bounded status request | Agent Zero bridge | No new owner result captured in this report | `HISTORICAL EVIDENCE`: prior bounded bridge contracts and runtime are documented; household delegation remains denied. |

Recipes, web search, Channels, and safe Grocy mutation/read-back have fresh prior owner evidence in the repository, but are not relabelled as newly re-proven here. Finance mutation and destructive homelab actions were not attempted by design.

## 7. Multi-user/authority

The minimal authentication smoke was run against `/api/v1/auths/ldap` with the protected credential files; only non-secret identity fields were emitted:

| Label | Login | Resolved subject | Role field | Current configured resource mapping |
|---|---|---|---|---|
| Owner | HTTP 200, session returned | `45ed2520-fc29-411d-ae70-05d8df655898` | `user` | owner path: Core health, Grocy, backup |
| Household A | HTTP 200, session returned | `d5e8a4f3-63fd-48d3-99b9-761f0531969f` | `user` | Core health, Grocy, backup |
| Household B | HTTP 200, session returned | `53c31d45-321a-4533-8e99-d2c5458a60d1` | `user` | Grocy only |

This proves distinct session establishment and the configured subject mapping; it does not by itself prove every DOM policy branch. The Phase 2 DOM matrix and repository contracts provide `HISTORICAL EVIDENCE` for private conversation/memory isolation, shared Grocy, finance denial, Agent Zero denial, mutation denial, stale-tab handling, and revocation. Phase 3’s current staged authority-aware catalog is `SYNTHETIC VERIFIED`: B’s catalog excludes Core health and backup, A’s includes its explicit grants, and revoked authority is rechecked before control/share/create.

No household workflow sharing grants finance, private memory, credentials, Agent Zero, or homelab mutation. The server-side policy is the protection; UI hiding alone is not treated as sufficient. Current product caveat: exact current LLDAP group membership was not printed by the auth response, so group-name resolution is `UNVERIFIED` beyond the deployed subject/resource mapping.

## 8. Memory

Hindsight health is `LIVE VERIFIED` (healthy, connected database). A fresh unique retain → end conversation → genuinely new conversation → natural recall proof passed after the asynchronous retain completed:

- RETAIN: `LIVE VERIFIED` for the harmless synthetic marker above.
- RECALL from fresh session: `LIVE VERIFIED` after asynchronous indexing.
- BANK / memory class: `LIVE VERIFIED` — `hades-owner`, explicit-memory tag.
- RESULT: `LIVE VERIFIED` correctness; freshness/latency SLO remains `UNVERIFIED` because the worker backlog delayed indexing substantially.

No private memory content is reproduced.

## 9. Failure/recovery

The live core dependency health baseline is good: n8n `/healthz` returned `status=ok`; Hindsight returned healthy/database-connected; LLDAP was healthy; Open WebUI returned 200; all core containers were running. Representative failure semantics from the recent Phase 2 campaign remain `HISTORICAL EVIDENCE`, including bounded dependency failure, retry/unknown-outcome behavior, stale-tab reconciliation, and notification safety. They were not wholesale re-crashed for this report.

Current classifications:

- Inference outage, SearXNG failure, Grocy outage, STT/TTS failure, tool timeout, abandoned generation: `HISTORICAL EVIDENCE` for recent bounded fixtures; fresh current behavior `UNVERIFIED`.
- Arbitrary n8n failure recovery: `DEFERRED`; Phase 3 does not exercise arbitrary graphs.
- Authority broadening during failure: `SYNTHETIC VERIFIED` in Phase 3 contracts; no resource mutation or n8n promotion is performed.
- Product-state duplicate health watches: `BROKEN`; cleanup/reconciliation is required before calling the owner watch surface reliable.

## 10. Automation / Agent Zero / JEV readiness

- n8n is deployed and healthy on loopback — `LIVE VERIFIED` — but current authorized workflows are bounded and typed. It is not an unrestricted household workflow builder.
- Epsilon Phase 2 contracts and accepted typed workflows are deployed — `LIVE VERIFIED` for the accepted boundary; recent closure evidence is also `HISTORICAL EVIDENCE` where not re-run.
- Phase 3 catalog/metadata/policy is implemented in the local repository and deployed behind `HADES_EPSILON_PHASE3_HOUSEHOLD_CREATION=staged` — `REPOSITORY VERIFIED` + `LIVE VERIFIED`. It stores staged automation metadata in SQLite and deliberately does not create n8n graphs.
- Agent Zero is a live bounded subordinate runtime — `LIVE VERIFIED` — but its operator route is owner-gated and not a household capability.
- A JEV-like architecture is not integrated as a runtime — `NOT STARTED` / `DEFERRED`. Existing pieces are Hermes policy/tool routing, Agent Zero delegation, n8n execution, Open WebUI sessions, MCP adapters, Hindsight, and Phase 3 persistent metadata. A future JEV would need to coordinate these under the existing authority boundary; it should not silently replace policy, memory, or the owner-facing composer.
- Personal workspaces, task persistence, event-driven automation, and proactive execution beyond the bounded Epsilon surfaces are `STAGED` or `PREPARATION ONLY`.

## 11. Backup/recovery

Fresh HADES guest evidence found current Git rollback artifacts:

- `$HADES_HOME/generated-full/backups/epsilon-phase2-custody/hades-latest.bundle` (1,154,798 bytes)
- `$HADES_HOME/generated-full/backups/epsilon-phase2-custody/hades-infra-latest.bundle` (604,203 bytes)

These are `LIVE VERIFIED` as files on HADES Core. The live service also exposes a configured backup evidence path and the accepted Backup Verification surface.

storage host `<PRIVATE_LAN_ADDRESS>` answered TCP/22 and TCP/8006, but the available noninteractive `scotty` SSH identity was not accepted. Current `tank` health, latest storage host bundles/checksums, and encrypted custody are therefore `EXTERNAL-GATED` / `UNVERIFIED` in this run. storage host is same-homelab storage, not offsite custody.

Recovery conclusions: HADES guest failure has documented same-site rollback artifacts (`HISTORICAL EVIDENCE` plus live local artifacts); hypervisor host failure and storage host failure are `UNVERIFIED`; whole-site loss survival is `BROKEN` as a proven property / `EXTERNAL-GATED` until independently held encrypted custody is demonstrated.

## 12. Product usability

If Scotty opens HADES now, he can reliably use authenticated chat, Grocy household reads, bounded health/backup checks, owner-only homelab read surfaces, selected search/research, and existing owner-only integrations. Another household member can reliably use explicitly shared household reads and the Phase 2 household-scoped surfaces; private memory, finance, Agent Zero, and mutations remain denied.

Awkward areas are the inconsistent homelab answer composition, stale duplicate health-watch state, and the fact that model/preset routing is not transparent enough to the owner. Impressive but not daily-use features include the broad Agent Zero runtime, extensive test harnesses, and synthetic typed automation contracts; they are not evidence of autonomous household utility. Admin/Luna intervention is still required for deployment, identity/group changes, n8n promotion, production workflow creation, recovery custody, and privileged homelab changes.

Likely week-one abandonment risks are stale/duplicate automation state, unclear failure outcomes, overly narrow natural-language routing, and the boundary between “available in code” and “available in the owner UI.” Five highest-value current workflows: household inventory/read-back, daily health visibility, backup evidence, recipe-to-Grocy assistance, and owner-only homelab/search research.

## 13. Roadmap matrix

| Domain | Current classification |
|---|---|
| Chat | `DAILY USABLE` |
| Model routing | `DOGFOOD USABLE`; exact preset bindings partly `UNVERIFIED` |
| Memory | `DOGFOOD USABLE` historically; fresh new-fact proof `UNVERIFIED` here |
| Grocy/household | `DAILY USABLE` for bounded reads; safe mutation `DOGFOOD USABLE` |
| Recipes | `DOGFOOD USABLE` |
| Finance | `OWNER-GATED` |
| Homelab read | `DOGFOOD USABLE` with answer-composition gaps |
| Homelab control | `OWNER-GATED` |
| Self-service workloads | `STAGED` |
| Web research | `DOGFOOD USABLE` |
| Browser interaction | `STAGED` / privileged interaction `DEFERRED` |
| Voice | `STAGED`; listener live, end-to-end fresh proof `UNVERIFIED` |
| Home Assistant | `DEFERRED` / `OWNER-GATED` |
| Agent Zero | `DOGFOOD USABLE` owner-bounded; household `OWNER-GATED` |
| Automation/n8n | `ENGINEERING GREEN` for bounded contracts; unrestricted creation `NOT STARTED` |
| Multi-user | `DOGFOOD USABLE` |
| Channels/shared collaboration | `DOGFOOD USABLE` with owner-scope boundary |
| Personal workspace/device integration | `PREPARATION ONLY` |
| JEV-style execution | `NOT STARTED` |
| Backup/recovery | `STAGED` same-site; whole-site recovery `EXTERNAL-GATED` |

## 14. Drift/waste findings

1. `BROKEN / owner value`: duplicate health-watch records are visible to the owner. The product is spending attention on acceptance plumbing while stale staged state remains in the daily surface.
2. `REPOSITORY VERIFIED / architectural risk`: HADES has accumulated many one-off contracts and DOM harnesses. They are justified when they prove authority, stale-tab, revocation, or failure invariants, but should not be mistaken for product capability. Phase 3 is intentionally kept as a small typed catalog rather than an arbitrary workflow framework.
3. `UNVERIFIED / documentation drift`: public GitHub does not contain the current local HEAD, and infra has no configured upstream. Any external advisor reading only public source will miss current Phase 3 work.
4. `GOOD COMPLEXITY`: server-side authority checks, explicit confirmation, canonical backend read-back, subject isolation, and separate staged metadata are justified safety complexity.
5. `DRIFT RISK`: display names such as Code, Creative, and Security Lab can look productized while current physical route/preset bindings are not freshly proven. The owner-facing model catalog should expose actual route provenance.

## 15. Recommended next actions

1. Reconcile and remove duplicate/unknown health-watch records, then prove owner listing against canonical state. **Luna:** yes. **Closure proof:** one canonical record per intended watch and a fresh DOM listing.
2. Finish Phase 3 staged DOM acceptance across Owner/A/B: discovery, preview/confirm, ownership, quotas, duplicate prevention, lifecycle, sharing, revocation, removed-user handling, stale tab, double submit, and mobile sizes. **Luna:** yes. **Closure proof:** persistent multi-user matrix with clean SQLite audit and no n8n promotion.
3. Publish the Phase 3 Manny decision packet: exact templates, owner/admin role, resource grants, quotas, promotion boundary, revocation semantics, and rollback. **Luna:** draft autonomously; **Scotty/Manny:** required for production authorization.
4. Make deployed revision provenance machine-readable in the service/image metadata. **Luna:** yes. **Closure proof:** live endpoint reports a source SHA matching a checked-out artifact.
5. Re-run a short fresh Hindsight unique-fact retain/close/new-session recall proof. **Luna:** yes. **Closure proof:** harmless marker, bank/type, recall result, cleanup.
6. Repair homelab status composition so a concise node request returns node inventory plus blockers rather than only Core Watch. **Luna:** yes. **Closure proof:** owner DOM prompt with canonical source references.
7. Re-establish storage host read access or have Scotty provide a sanctioned read-only path for ZFS/checksum evidence. **Scotty/external gate:** required if credentials/route are unavailable. **Closure proof:** fresh `zpool status -x`, dataset, bundle, checksum, and custody evidence.
8. Verify actual Open WebUI preset-to-endpoint mappings and voice end-to-end health, without changing routing. **Luna:** yes where endpoints are available; **Scotty:** only if owner UI configuration is gated.
9. Keep unrestricted household workflow creation disabled until the decision packet is accepted; do not build JEV yet. **Luna:** yes. **Closure proof:** staged gate remains non-mutating and the authorization decision is recorded.

## 16. Proof appendix

### Source and deployment

**CLAIM:** HADES source HEAD and dirty state.
**COMMAND:** `git -C $HADES_HOME/Hades status --short --branch; git -C $HADES_HOME/Hades rev-parse HEAD`
**RESULT:** `main...origin/main [ahead 542]`; HEAD `e609fec`; Phase 3 files uncommitted.
**CLASSIFICATION:** `REPOSITORY VERIFIED`

**CLAIM:** Infra source HEAD and clean state.
**COMMAND:** `git -C $HADES_HOME/hades-infra status --short --branch; git -C $HADES_HOME/hades-infra rev-parse HEAD`
**RESULT:** clean `main`; HEAD `bf648f5`; no upstream configured.
**CLASSIFICATION:** `REPOSITORY VERIFIED`

**CLAIM:** Deployed Hermes runtime.
**COMMAND:** `ssh scotty@<PRIVATE_LAN_ADDRESS> 'systemctl show hades-hermes.service -p ExecStart -p WorkingDirectory; systemctl is-active hades-hermes.service'`
**RESULT:** `/opt/hades-hermes-0.21.2/bin/hermes`; workdir `$HADES_HOME/Hades-reconciled-b102dfd`; `active`.
**CLASSIFICATION:** `LIVE VERIFIED`

### HADES guest and core services

**CLAIM:** HADES guest core containers are running.
**COMMAND:** `ssh scotty@<PRIVATE_LAN_ADDRESS> 'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"'`
**RESULT:** Open WebUI `58c3ea6213a9`; Hermes host service; Hindsight `84ab276b8f50`; Agent Zero `680ab243d358`; Grocy `8449aff56e6b`; LLDAP healthy; SearXNG; n8n `9f693fd55655` healthy; OCR `20260918-r3`.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Hindsight health.
**COMMAND:** `curl http://127.0.0.1:8888/health` on HADES guest.
**RESULT:** `{"status":"healthy","database":"connected",...}`.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** n8n health.
**COMMAND:** `curl http://127.0.0.1:5678/healthz` on HADES guest.
**RESULT:** `{"status":"ok"}`.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Open WebUI and LLDAP paths.
**COMMAND:** loopback/host HTTP probes for `<PRIVATE_LAN_ADDRESS>:3000` and `127.0.0.1:17170`.
**RESULT:** both returned HTTP 200.
**CLASSIFICATION:** `LIVE VERIFIED`

### Authentication

**CLAIM:** distinct current authenticated subjects.
**COMMAND:** POST `/api/v1/auths/ldap` for protected Owner/A/B credentials; emit only label, HTTP code, subject id/name, role, session-present.
**RESULT:** Owner `45ed2520-...`; A `d5e8a4f3-...`; B `53c31d45-...`; all HTTP 200 with sessions; all role field `user`.
**CLASSIFICATION:** `LIVE VERIFIED`; group-name projection `UNVERIFIED`.

### Model endpoints

**CLAIM:** current inference endpoints/models.
**COMMAND:** GET `/api/tags` and `/v1/models` on `<PRIVATE_LAN_ADDRESS>:11435`, `<PRIVATE_LAN_ADDRESS>:11437`, `<PRIVATE_LAN_ADDRESS>:11434`.
**RESULT:** fast inference provider `qwen3:8b`; deep inference provider `qwen3.6:35b` plus aliases; specialized inference provider `gemma4:e4b` plus embedding model.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** voice listener reachability.
**COMMAND:** GET `http://<PRIVATE_LAN_ADDRESS>:8766/`.
**RESULT:** HTTP 404 from a live HTTP server.
**CLASSIFICATION:** `LIVE VERIFIED` listener; end-to-end voice `UNVERIFIED`.

### Topology and recovery

**CLAIM:** known live network reachability.
**COMMAND:** bounded ICMP checks for `.2`, `.3`, `.69`, `.73`, `.152`, `.156`.
**RESULT:** reachable; `.155` was unreachable. storage host `.2` TCP/22 and `:8006` open.
**CLASSIFICATION:** `LIVE VERIFIED` reachability only.

**CLAIM:** local rollback bundles exist.
**COMMAND:** `find $HADES_HOME/generated-full/backups -maxdepth 4 -type f \( -name '*.bundle' -o -name '*.sha256' \)` on HADES guest.
**RESULT:** current HADES and infra bundles in `epsilon-phase2-custody`.
**CLASSIFICATION:** `LIVE VERIFIED` local artifacts; custody/whole-site recovery `EXTERNAL-GATED`.

**CLAIM:** storage host ZFS health.
**COMMAND:** bounded SSH `scotty@<PRIVATE_LAN_ADDRESS> 'zpool status -x'`.
**RESULT:** TCP reachable but available noninteractive identity not accepted.
**CLASSIFICATION:** `EXTERNAL-GATED` / `UNVERIFIED`; no ZFS claim made.

### Phase 3 staged proof

**CLAIM:** typed self-service policy contracts.
**COMMAND:** `bash scripts/test-phase3-self-service.sh`.
**RESULT:** `PASS Phase 3 self-service policy, ownership, quota, revocation, sharing, and admin contracts`.
**CLASSIFICATION:** `SYNTHETIC VERIFIED` (the word PASS here is the test output, not a production-status declaration).

**CLAIM:** staged gate is enabled without unrestricted promotion.
**COMMAND:** `systemctl show hades-hermes.service` and deployed drop-in.
**RESULT:** `HADES_EPSILON_PHASE3_HOUSEHOLD_CREATION=staged`; Phase 3 module is deployed; n8n remains loopback and no Phase 3 n8n graph is created.
**CLASSIFICATION:** `LIVE VERIFIED` for staged deployment; production household creation `DEFERRED` / `OWNER-GATED`.

**CLAIM:** Phase 3 household authority and sharing boundary.
**COMMAND:** Authenticated DOM sessions for Household A and B, with staged gate live: catalog, create, list, share, bounded run, revoke, list.
**RESULT:** A created Server Health and Low Grocery staged records; B catalog exposed only Low Grocery and Groceries-only Weekly Summary; B server request was denied; B could run a shared Low Grocery record, then saw no staged automations after A revoked sharing. No n8n workflow was created.
**CLASSIFICATION:** `LIVE VERIFIED` for the tested staged boundary.

**CLAIM:** Phase 3 implementation contracts remain green after the authority fix.
**COMMAND:** `bash scripts/test-phase3-self-service.sh; python3 -m py_compile hermes/sitecustomize.py integrations/automation/phase3_self_service.py`
**RESULT:** self-service policy/ownership/quota/revocation/sharing/admin contract test passed; Python compilation passed; staged test tables were cleared afterward.
**CLASSIFICATION:** `SYNTHETIC VERIFIED`.
