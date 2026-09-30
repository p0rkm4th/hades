# HADES LIVE-STATE ADVISOR HANDOFF

**Timestamp:** 2026-09-24 15:14 UTC / 2026-09-24 America/Chicago
**Evidence boundary:** Fresh checks used the authenticated Open WebUI DOM, VM 802 live services, canonical Grocy, deployed Hermes, local source repositories, and bounded repository contracts. Synthetic fixtures are labelled as such. No passwords, tokens, private financial data, private memory content, destructive homelab actions, arbitrary n8n mutation, or external notification was used.

## 1. Executive state

HADES is a local-first owner/household assistant on HADES Core VM 802. The owner-facing Open WebUI and Hermes gateway are live. Current useful product surfaces are authenticated chat, canonical Grocy household reads/writes, bounded health/backup workflows, selected web/search, owner-only homelab reads, durable bounded task state, and owner-only read-only finance analysis from the explicitly authorized `bk_download.csv` statement. Homelab telemetry now composes live Proxmox, NetBox, and Uptime Kuma inputs, but guest OS/service/network-trend data remain absent.

**Campaign result:** `LIVE VERIFIED` 15/15 useful seed workflows in one persistent authenticated owner session, plus a new combined 20/20 Owner/Household A/Household B soak across desktop, 390x844, and 320x568. That soak covered stale-tab abandonment/recovery, double-submit protection, shared Weekly history, revocation boundaries, mixed task prompts, and the repaired recipe-availability turn. Finance CSV workflows return live, owner-only historical analysis; current balances/future obligations remain unavailable. Homelab is materially improved but not a full guest/service/network diagnostic. Epsilon Phase 2 is `DOGFOOD GREEN` on the accepted happy paths; deliberate live source-outage injection is `UNVERIFIED`/`DEFERRED` because it would require disabling a production dependency or modifying the approved n8n graph, not because of an observed regression.

**Post-auth-refresh replay (`2026-09-24`, `LIVE VERIFIED`):** the required
minimal authentication smoke succeeded for Acceptance Owner, Household A, and
Household B with distinct subjects and fresh sessions; all resolved to the
expected application role, with no owner fallback or cross-user subject reuse.
The auth response does not expose LDAP group names, so exact group-name display
remains `UNVERIFIED`; effective household grants are verified separately by
server-side DOM behavior.

**Superseding read-only deployment provenance audit (`2026-09-24`, auditing
the service state present at this report's 15:14 UTC capture):** SSH confirmed
`hades-hermes.service` remains
active on Hermes `0.21.2`, with `NRestarts=0` and process start `15:07:50Z`.
The provenance JSON still reports HADES `bcd81f4...`, infra `bf648f...`, and
overlay hash `1863ed16...`, generated at `07:54:33Z`. Systemd's effective
`PYTHONPATH`, however, selects `$HADES_HOME/generated-full/config/overlay`,
whose active `sitecustomize.py` hash is `2157f732...`. The provenance overlay
hash instead matches the modified source file in the detached deployment
checkout, whose Git HEAD is `b102dfd...`; the generated overlay does not match
the reported digest. The active overlay's Task handler matches the Alpha
implementation and lacks the Beta completed-history and task-ID branches.
Therefore this later check supersedes the previous `LIVE VERIFIED` claim of
fresh current provenance. Runtime identity is `STALE / CONTRADICTED`; no
production file or service was modified.

The exact expanded owner prompt corpus was replayed in one authenticated DOM
session and settled 15/15 turns, with no timeout: recipe availability; pantry
expiry and meal use; spaghetti inventory/grocery-list request; homelab status;
network diagnosis; model placement; backup coverage; utilities; restaurants and
delivery; subscriptions; weekend affordability; lease-prepayment goal;
restock; a $300 savings target; and the morning briefing. Follow-up,
correction, genuinely fresh-session, and 390x844 continuation turns also
settled. The replay did not execute a grocery-list or finance mutation. Recipe,
expiry, restock, homelab, network, backup, and briefing responses contained the
expected bounded/canonical domain signals. Finance history prompts stayed
within the owner-only/read-only boundary; current-balance, future-obligation,
and lease-planning prompts did not invent a spend number. This is evidence of
response behavior, not proof that every requested workflow is fully
productized.

**Fresh memory correction (`LIVE VERIFIED`):** the first post-auth-refresh
probe reproduced two live defects: Tartarus-backed Hindsight extraction was
timing out, and the small extraction model could preserve a marker as an entity
while dropping its exact value from fact text. Hindsight was moved to the
already-running Hermes Compute local `qwen3:8b` lane, and explicit owner-memory
retains now attach the user-approved fact as a canonical Hindsight entity. The
deployed overlay and generated Hindsight record were backed up before change.
The fresh retain → genuinely new conversation → natural recall proof now
returns the new marker (`LIVE VERIFIED`); no static memory fallback or other
user bank is used. Hindsight backlog/SLO timing remains `DEFERRED` pending a
longer low-load observation.

**Isolated extraction-route dispatch (`SYNTHETIC VERIFIED`, 2026-09-25):** the
pinned Hindsight image (`sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`)
received a synthetic retain request and dispatched extraction calls to a local
mock model endpoint configured with the same `HINDSIGHT_API_LLM_BASE_URL` and
model settings used by the tracked Compose contract. The mock observed `/api/chat` and
`/v1/chat/completions` requests with the selected synthetic model name. The
repeatable harness is [`scripts/test-hindsight-route-runtime.py`](../scripts/test-hindsight-route-runtime.py);
it removed its disposable container and volume after the run. This verifies
endpoint dispatch only: the stub response does not establish extraction
quality, natural recall, production routing, or a latency SLO. No production
memory or model route was touched.

**Fresh authority discovery (`LIVE VERIFIED`):** the staged, non-mutating DOM
discovery matrix settled for all three identities across desktop, tablet,
390x844, and 320x568 (12/12 rows). It advertised no external notification,
shell, Agent Zero, or automatic-remediation capability and performed no
production enablement.

**Latest provenance-recorded source:** HADES `bcd81f435c4d8a6210802ffeb64c20a0ad3adbd7`; infra `bf648f52f5ab0e4da9ebd811f9ccc6866cf5341a`. The later service-path audit below found the active generated overlay hash differs from this record.
**Deployed revision:** Hermes `0.21.2` is `LIVE VERIFIED` active; exact loaded overlay/source identity is `STALE / CONTRADICTED` by the later audit.  
**Highest-value conclusion:** HADES is advancing product value where canonical household data and bounded authority exist; the main remaining value blockers are finance authorization/data, richer homelab telemetry, and productized fresh-session/task continuity—not more infrastructure scaffolding.

**Phase 2 gate snapshot:** Server Health Watch, Backup Verification, Low Inventory Summary, and Weekly Household Summary are `DOGFOOD GREEN`/`LIVE VERIFIED` on their approved happy paths, with sharing/revocation and typed failure fixtures `LIVE VERIFIED`/`REPOSITORY VERIFIED`. The combined multi-user viewport soak is `LIVE VERIFIED` from the completed 20/20 run; a later rerun exposed a harness page-closure issue and is not counted as a pass. Current P0/P1 ledger: zero observed in this campaign (`LIVE VERIFIED` bounded DOM/privacy/action evidence plus `REPOSITORY VERIFIED` contracts). Deliberate live source-outage injection remains `UNVERIFIED`/`DEFERRED` as an authority-limited evidence gap, not a Phase 2 regression.

## 2. Source/deployment revisions

| Repository | Evidence |
|---|---|
| HADES | `REPOSITORY VERIFIED`: branch `main`, current HEAD `bcd81f435c4d8a621...`, with the report and local DOM probe-helper changes unstaged; `origin/main` is behind by 641 commits. The deployed product source is the current product HEAD `bcd81f4`; the unstaged changes are test/report artifacts. |
| hades-infra | `REPOSITORY VERIFIED`: branch `main`, HEAD `bf648f52...`, clean working tree; no configured upstream, so public parity is `UNVERIFIED`. |
| Current campaign start | `REPOSITORY VERIFIED`: first repair commit `972ceb8` routed recipe inventory questions to canonical Grocy. |
| Current campaign end | `REPOSITORY VERIFIED`: `bcd81f4` prevents stale homelab/provisioning history from stealing a current recipe turn and includes the combined multi-user/multi-viewport soak. |
| Live runtime | `LIVE VERIFIED`: `hades-hermes.service` active; working directory `$HADES_HOME/Hades-reconciled-b102dfd`; overlay `$HADES_HOME/generated-full/config/overlay/sitecustomize.py`. |
| Revision identity | `LIVE VERIFIED`: `/v1/epsilon/provenance` reports deployed HADES `bcd81f4...`, infra `bf648f5...`, overlay `1863ed16...`, manifest `811807...`, and `2026-09-24T07:54:33Z`. |

Recent meaningful HADES commits: `0d34d62` shared-history/revocation probes, `9a7837c` unrelated-stale-state handling on Weekly reads, `7874352` latest-history routing, `5769bdb` shared Weekly result history, `1755a35` regression coverage, `f3f9132` Weekly health projection and Backup confirmation recovery, `f2d7910` unshared Phase 2 read wording and probe harness, `794a6f4` weekly summary status, `6627afe` plural weekly-summary intent, `ee9d067` typed Phase 2 summary precedence, `4d5fc9a` grocery correction precedence, `91d2be1` compound-briefing precedence over finance shortcut, `bae1e28` bounded finance short-circuit and websocket-aware DOM settlement, `c77f957` duplicate Health Watch selection, `f25e2ac` shared-recipient reconciliation, `85cfc9f` typed Health Watch precedence over staged automation, `c8d5451` named-watch natural-language routing, `9617472` cross-worker confirmation precedence, `61ac9b4` finance/upload UX and spaghetti draft, `e99ce70` finance CSV/telemetry wiring, `c837042` telemetry inputs, `2cae60d` runtime evidence, `d7a3131` VM runtime detail, `d6e71c2` private-domain proof, `5b707b4` memory denial, `446bb4` recipe corpus, `6efff7e` canonical recipe inventory, `d8e9b04` fresh briefing proof. Relevant tags include `decision-plane-alpha-baseline`, `gamma-adversarial-dogfood`, `gamma-adversarial-preflight`, and `daily-driver-reliability-beta` (`REPOSITORY VERIFIED`).

## 3. Live topology

| System | Current state |
|---|---|
| Erebus / Proxmox `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` reachable; Proxmox API path configured. Full privileged host/resource state `UNVERIFIED`. |
| HADES Core / VM 802 `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED`; Open WebUI, Hermes, Grocy, Hindsight, SearXNG, LLDAP, Agent Zero, OCR, and n8n paths are active. |
| Agent Zero / VM 801 | `UNVERIFIED` as a separate VM; current deployed Agent Zero runtime is container `hades-agent-zero` on VM 802. |
| Alexandra `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` TCP reachability; ZFS/backup state `EXTERNAL-GATED` because the available noninteractive identity was rejected. Not offsite. |
| Alexandra service guest / 803 `<PRIVATE_LAN_ADDRESS>` | `HISTORICAL EVIDENCE`; not re-probed in this campaign. |
| Tartarus `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama on `:11437`; Deep inference role. |
| Hypnos `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama on `:11434`; specialized/code and embedding availability. |
| Hermes Compute `<PRIVATE_LAN_ADDRESS>` | `LIVE VERIFIED` Ollama `:11435` and voice listener `:8766`; fast inference/voice. Distinct from Hermes Agent. |
| Thanatos `<PRIVATE_LAN_ADDRESS>` | `HISTORICAL EVIDENCE`; current reachability not independently re-established here. |

Open ports and ICMP are treated as reachability only. They do not prove OS, GPU health, workload capacity, or backup correctness.

## 4. Core services

| Capability | Live evidence and boundary |
|---|---|
| Open WebUI | `LIVE VERIFIED`: authenticated owner DOM at the production URL; container exposed through VM 802. |
| Hermes Agent | `LIVE VERIFIED`: systemd service active, Hermes `0.21.2`; policy/tool boundary. |
| Hindsight | `LIVE VERIFIED`: health endpoint healthy and database connected; fresh-memory correctness proven previously, latency remains a concern. |
| SearXNG | `LIVE VERIFIED`: loopback service/root reachable; web failure boundary contract is `REPOSITORY VERIFIED`. |
| Grocy | `LIVE VERIFIED`: live canonical API path on loopback `:7003`; recipes, stock, expiry, and shopping-list reads are used by owner routes. |
| LLDAP/auth | `LIVE VERIFIED`: LDAP auth succeeded for Owner, Household A, and Household B with distinct subjects; exact group-name projection is `UNVERIFIED`. |
| Agent Zero | `LIVE VERIFIED` runtime; delegation is owner-gated and household denial is server-side. |
| homelab MCP/control | `REPOSITORY VERIFIED` read-only adapter; live owner reads are partial. Mutations remain unauthorized. |
| Finance | `LIVE VERIFIED` for owner-only read-only CSV analysis; `EXTERNAL-GATED` for live Actual Budget balances/import. |
| Voice | `LIVE VERIFIED` listener reachability at Hermes Compute `:8766`; end-to-end STT/TTS is `UNVERIFIED`. |
| n8n | `LIVE VERIFIED`: container and health endpoint active; arbitrary graph creation remains unauthorized. |
| Home Assistant | `DEFERRED` / `OWNER-GATED`; no current owner-facing authorized path was enabled. |

## 5. Models/routing

| Route | Current evidence |
|---|---|
| Hades Fast | `LIVE VERIFIED`: Hermes Compute `:11435`, `qwen3:8b` available. |
| Hades Deep | `LIVE VERIFIED`: Tartarus `:11437`, `qwen3.6:35b` available. Exact per-prompt selection `UNVERIFIED`. |
| Code | `LIVE VERIFIED` endpoint availability: Hypnos `:11434`, `gemma4:e4b`; display binding `UNVERIFIED`. |
| Creative / Uncensored Writing / Security Lab | `UNVERIFIED`: current physical display-preset bindings were not proven from live endpoint inventory. |
| Embedding | `LIVE VERIFIED`: `nomic-embed-text` available on Hypnos; exact Hindsight selection `UNVERIFIED`. |
| Voice | `LIVE VERIFIED` listener; STT/TTS runtime and latency `UNVERIFIED`. |

Historical assumptions remain partly true: Tartarus qwen3.6:35b on `:11437`, Hermes Compute fast on `:11435`, Hypnos specialized inference on `:11434`, and Hermes Compute voice on `:8766`. The old blanket `64K` context claim is `UNVERIFIED`.

## 6. Real owner dogfood: all 15 seed workflows

The collector used the actual authenticated HADES UI and fresh chat isolation. The isolated corpus file is `/tmp/hades-exhaustive-isolated4-report.json` (`LIVE VERIFIED` evidence artifact). Responses below are summarized without private data.

| # | Workflow | Result | Classification / remaining issue |
|---:|---|---|---|
| 1 | List recipes and say which are makeable | Canonical Grocy returned all three live recipes, each currently makeable from stock. | `LIVE VERIFIED`; recipe inventory route repaired and expanded. |
| 2 | Expiring food and meals | Canonical Grocy identified expired synthetic milk and recipe overlap; no write. | `LIVE VERIFIED`; no future-expiry item currently known. |
| 3 | Spaghetti: inspect, missing items, add list | Fresh authenticated single-submit DOM turn completed with `HADES Owner Spaghetti Draft`, five invented baseline ingredients, missing shopping items, and no Stop state; canonical Grocy recipe/positions/list read-back agrees. | `LIVE VERIFIED`; no pantry stock fabricated. |
| 4 | Full homelab status | Fresh owner DOM now lists Alexandra/Erebus plus VM 801/802/852, with live CPU and memory and bounded Proxmox disk allocations; guest OS, major services, GPU, and network trends remain explicitly unknown. | `LIVE VERIFIED` useful partial; guest OS/service/network composition `DEFERRED`. |
| 5 | Network slowdown diagnosis | Returned current VM/memory evidence and explicitly disclosed absent network-health telemetry and historical trends. | `LIVE VERIFIED` honest partial; `BROKEN` as a complete diagnostic product. |
| 6 | Best model deployment location | Refused recommendation because verified GPU/VRAM/current-load telemetry is insufficient; no deployment. | `OWNER-GATED`/telemetry-gated; safe but not useful enough. |
| 7 | Backup coverage | Owner now has live HADES and infrastructure Backup Checks; both execute through n8n and return canonical verification state. | `LIVE VERIFIED` bounded checks; full service coverage remains incomplete. |
| 8 | Utilities average | Owner-only CSV analysis returned 539 usable rows covering 2026-01-02 through 2026-09-10, pending count, classified utility totals, and a historical monthly average; no live balance was implied. | `LIVE VERIFIED` historical CSV; current ledger `EXTERNAL-GATED`. |
| 9 | Restaurant/DoorDash/coffee | Owner-only CSV analysis returned monthly totals and top statement-description groups without exposing rows in this report. | `LIVE VERIFIED` historical CSV; merchant semantics limited by statement descriptions. |
| 10 | Recurring charges/subscriptions | CSV analysis found recurring description groups and amount-increase candidates, but explicitly declined to infer usage or true duplicates. | `LIVE VERIFIED` bounded analysis; usage `UNVERIFIED`. |
| 11 | Safe weekend spend | Correctly refused to invent a number because the CSV lacks current balances, future bills, and future paychecks. | `LIVE VERIFIED` safe limitation; `EXTERNAL-GATED` decision inputs. |
| 12 | Lease-prepayment goal | Correctly refused to invent a goal gap or paycheck schedule from transactions alone. | `LIVE VERIFIED` safe limitation; target data `OWNER-GATED`. |
| 13 | Household restock | Canonical Grocy stock and shopping-list read; no synthetic consumption history. | `LIVE VERIFIED`; historical velocity still `DEFERRED`. |
| 14 | Cut spending by $300 | Historical CSV analysis identified reviewable discretionary categories and disclosed that a guaranteed $300 reduction cannot be proven from the file alone. | `LIVE VERIFIED` bounded analysis. |
| 15 | Morning briefing | Composed bounded homelab, backup, household, expiry, and owner-only authorized CSV finance coverage; current balances and future bills remain explicitly unavailable. | `LIVE VERIFIED` composition; homelab and finance are partial. |

The repair set addressed recipe-route collisions, expiry reads, spaghetti honesty, model-placement hallucination, finance/backup/restock intent collisions, backup coverage wording, network-telemetry overclaiming, and inference-failure UI liveness. No authority expansion was made.

### Combined Phase 2 soak

The latest deployed build passed one combined persistent browser process with 20/20 settled turns: Owner desktop/mobile recipe, expiry, restock, subscription, briefing, homelab, network, and backup/double-submit paths; Household A shared Weekly history; and Household B denial. The matrix used 1440x900, 390x844, and 320x568 contexts and included stale-tab abandonment/recovery and a shared-resource boundary. The recipe turn initially exposed a real stale-context defect: old homelab/provisioning words in prior history could steal a current recipe request. The deployed `bcd81f4` fix makes current-turn text authoritative for those route guards; the post-fix combined run returned canonical Grocy recipes and completed 20/20 (`LIVE VERIFIED`).

## 7. Cross-domain composition, task, and canonical data

- Recipe availability and expiry use canonical Grocy recipe/stock data (`LIVE VERIFIED`); responses explicitly state when no write occurred.
- The original five recipe phrasings that previously produced unrelated answers were re-run in isolated authenticated sessions after deployment: makeable recipes, not-makeable recipes, saved recipes, “what recipes do we have,” and cooking recipes. All returned canonical Grocy output (`LIVE VERIFIED`).
- Restock reads canonical stock and shopping-list state (`LIVE VERIFIED`); consumption velocity is not synthesized.
- Morning briefing composes homelab, Backup Check, Grocy stock, expiry, and finance boundary responses (`LIVE VERIFIED`). A genuinely fresh DOM prompt asking what was learned from the briefing returned a live “morning briefing refresh” that re-read sources rather than pretending stale context was authoritative (`LIVE VERIFIED`). A two-turn same-chat harness once timed out during backend restart/transient model pressure; that is recorded as a bounded harness/runtime observation, not hidden as a pass.
- Durable Task state crossed `WAITING → AWAITING_APPROVAL → READY → RUNNING → COMPLETED` in earlier live acceptance, with SQLite revision/event read-back (`HISTORICAL EVIDENCE` reused; no active synthetic rows left).
- The owner explicitly authorized canonical spaghetti action and invented ingredients. HADES created an editable, clearly labeled Grocy draft and missing shopping products, with canonical recipe-position read-back. No pantry stock was fabricated. A fresh authenticated single-submit turn completed with no stale Stop state (`LIVE VERIFIED`).
- Recipe URL/paste ingestion remains available through the staged preview/apply MCP boundary. It preserves source URL/raw ingredient lines, rejects private URLs, requires exact product resolution, and requires explicit apply confirmation. Receipt-photo ingestion remains preview-first: local OCR, product review, and explicit pantry confirmation. It does not silently convert online photos or OCR guesses into pantry state.
- The post-deployment daily-use soak passed the finance CSV attachment stage and failed only during the novice-language stage on a 30-second turn timeout (`LIVE VERIFIED` runtime observation). The targeted abort/re-entry harness now passes with `Failed to fetch` recovery and no stale Stop control. A fresh standalone spaghetti owner turn now completes with canonical confirmation (`LIVE VERIFIED`).

### Phase 2 typed workflow read audit

The latest deployment repaired two real intent collisions found by live DOM probes: plural “low grocery summaries” previously fell through to a pantry read, and plural “weekly household summaries” previously fell through to staged Phase 3 metadata. Fresh owner reads now return typed status: Low Grocery Summary is enabled and reads current Grocy state; Weekly Household Summary is enabled and composes only approved Grocy, Server Health Watch, and Backup Verification results (`LIVE VERIFIED`). Owner Backup, Low Inventory, and Weekly execution probes now complete through the authenticated UI with canonical n8n read-back: Backup `HEALTHY`, Grocy `READY`, and Server Health `UP`, all `CURRENT` (`LIVE VERIFIED`). The Weekly graph previously silently omitted typed health state; the repaired bounded projection now preserves `UP` or `SOURCE_UNAVAILABLE` explicitly. Household A receives the typed weekly status through the shared read path; Household A/B receive explicit no-shared-record responses for unshared Backup/Low Inventory resources, and Household B receives the same for Weekly Summary (`LIVE VERIFIED`). Live n8n execution and freshness are now proven for the approved happy path. Controlled source-outage behavior and full per-recipient weekly partial-failure composition remain `UNVERIFIED`.

## 8. Multi-user, authority, and privacy

Minimal auth smoke (`LIVE VERIFIED`):

| Identity | Login | Subject | Role |
|---|---|---|---|
| Owner | HTTP 200/session | `45ed2520-fc29-411d-ae70-05d8df655898` | user |
| Household A | HTTP 200/session | `d5e8a4f3-63fd-48d3-99b9-761f0531969f` | user |
| Household B | HTTP 200/session | `53c31d45-321a-4533-8e99-d2c5458a60d1` | user |

No owner fallback or cross-user session reuse was observed in the authenticated soak (`LIVE VERIFIED`). Household shared Grocy reads work; household Agent Zero and finance requests are denied server-side; private memory and homelab mutation remain denied by policy. Revocation and stale-tab behavior have prior live evidence (`HISTORICAL EVIDENCE`) and repository contracts (`REPOSITORY VERIFIED`). Exact current LDAP group-name display is `UNVERIFIED`; subject/resource grants are the operative policy evidence. UI hiding alone is not treated as authorization.

Fresh household DOM checks after the latest deployment explicitly denied Household A's Scotty-finance request and Household B's Scotty-private-memory request before model invocation (`LIVE VERIFIED`). The responses revealed neither records nor whether a requested private marker exists.

## 9. Memory

Hindsight health is `LIVE VERIFIED`. The production route now uses the
 dedicated Hermes Compute local extraction lane, and the fresh owner-memory
 proof passes after a genuinely new conversation. Exact-value preservation is
 `LIVE VERIFIED` through canonical Hindsight entities; asynchronous backlog and
 a formal latency SLO remain `DEFERRED`. No private memory content is reproduced.

## 10. Failure/recovery

- Aborted live chat-completion request produced visible `Failed to fetch`, cleared the stale Stop/loading state, and recovered on a new `hello recovery` turn (`LIVE VERIFIED`).
- The first abort/re-entry harness result was a false green: its recovery assertion accepted an old assistant node from the previous conversation. The fixture now requires the New Chat control to clear all prior assistant nodes and requires a newly settled response. The corrected live run returned `Hello! How can I assist you today?`, with empty composer, no Stop control, and `new_response: true` (`LIVE VERIFIED` fixture evidence).
- Turn-liveness, web failure, task lifecycle, health-watch, Epsilon, and homelab read-only contracts are `REPOSITORY VERIFIED`.
- Full production SearXNG, Grocy, STT/TTS, and n8n outages were not intentionally induced; current live recovery is therefore `UNVERIFIED` for those dependencies.
- The normal weekly composition helper now preserves Backup and Server results when a Grocy reader raises, and emits an explicit `Unavailable this week: Groceries.` marker (`REPOSITORY VERIFIED`). This is a bounded fixture, not proof of a live n8n/source outage or end-to-end partial-failure execution; those remain `UNVERIFIED`.
- A bounded post-deploy DOM probe launched during the Hermes restart saw Open WebUI `Server Connection Error` and no completion event; after the service stabilized (`active`, `NRestarts=0`) the same 9-turn Phase 2 matrix settled successfully. This is `LIVE VERIFIED` transient restart behavior, not a claim of graceful restart continuity.
- Failure handlers do not broaden authority or silently guess unavailable finance/network data (`LIVE VERIFIED`/`REPOSITORY VERIFIED`).
- Health Watch dogfood exposed and repaired three real defects: named `HADES Core` actions were falling into the broader staged-automation route, cross-worker bare confirmations could replay stale create previews, and duplicate same-resource records were ambiguous. The deployed route now gives Household A a server-side view-only denial for `run HADES Core check`; owner recipient/state selectors allow deterministic reconciliation. One duplicate created by the earlier fixture was removed through the owner UI; one canonical watch remains (`LIVE VERIFIED`). Bare `yes` confirmation across a mixed stale-preview state still merits another clean soak before calling the workflow fully green (`UNVERIFIED`).
- A focused route regression reproduced the remaining bare-confirmation race: a stale worker-local create preview could override the current persisted share action, and the inverse stale-share/current-create sequence could also use the wrong intent. Commit `f34d51c` makes the current persisted preview authoritative for both directions; the route contract verifies no duplicate create and no stale share mutation (`REPOSITORY VERIFIED`). The current VM 802 overlay still has the older route logic, so this repair has not yet received authenticated production UI acceptance.
- The owner-authorized spaghetti recipe/list action had a check-then-write race across Hermes workers. The route now uses a dedicated cross-process recipe lock and the shared shopping-list lock around each canonical missing-item re-read/write. A two-process synthetic Grocy API fixture now verifies one recipe, five ingredient positions, and one shopping row per missing product (`REPOSITORY VERIFIED`). The active VM 802 overlay still has the prior unlocked route; the repair is not yet deployed.
- Phase 2 live execution exposed three additional defects and all are repaired: Weekly Summary merged the health endpoint's raw `{status:true}` without a typed projection, silently omitting server state; Backup Check bare confirmations could fall through to a stale Phase 3 action when multiple old pending records existed; and latest Weekly history language fell into staged Phase 3 metadata while unrelated pending state was present. The fixed Weekly graph emits `UP`/`SOURCE_UNAVAILABLE` with freshness, confirmation recovery filters to one current uncompleted matching Phase 2 action, and ordinary Weekly history ignores unrelated pending state (`LIVE VERIFIED`).
- A later combined-soak rerun exposed a test-harness-only defect: its top-level error handler masked the original browser failure by referencing a function-scoped `results` variable. The helper now has explicit login timeout/error reporting. A short diagnostic reached eight Owner desktop turns before a page-closure error in the combined helper's double-submit/stale-tab path; the dedicated three-viewport soak independently passed those fixtures. This is `REPOSITORY VERIFIED` harness repair plus `LIVE VERIFIED` focused fixture evidence, not a new product authorization or data-integrity defect.

## 11. Automation / Agent Zero / JEV readiness

n8n is deployed and healthy but bounded; arbitrary workflow creation is not enabled (`LIVE VERIFIED`). Agent Zero is a live subordinate runtime but owner-only (`LIVE VERIFIED`). Epsilon typed contracts are implemented and deployed; staged Phase 3 metadata deliberately does not create n8n graphs (`REPOSITORY VERIFIED` + `LIVE VERIFIED`). A JEV-like runtime is `NOT STARTED`: HADES already has pieces—Hermes policy, Open WebUI sessions, MCP adapters, Hindsight, Agent Zero delegation, n8n execution, SQLite task state—but no integrated proactive event/task runtime. Building JEV now would be lower value than closing canonical data and owner-visible workflows.

## 12. Backup/recovery

Local HADES and infra Git bundles exist under the VM 802 custody path (`LIVE VERIFIED`). Backup Check coverage exists for the recorded infrastructure repository; the campaign now exposes that coverage is not equivalent to “all important services” (`LIVE VERIFIED`). Alexandra is same-homelab storage, not offsite. Off-site custody/recovery was explicitly skipped per owner instruction and is `DEFERRED`/incomplete. Fresh ZFS health, encrypted custody, and whole-site loss recovery are not claimed.

## 13. Product usability

Scotty can reliably use owner chat, Grocy recipe/stock/expiry reads, owner-authorized spaghetti recipe/list setup, receipt/photo review, recipe URL/paste preview, historical finance CSV analysis, bounded health and backup checks, selected web research, and durable bounded task status. A household member can use explicitly shared household reads while finance, private memory, Agent Zero, and homelab mutations remain denied. The CSV upload affordance is contextual and visible after an attachment; it no longer asks the user to know an internal Actual account ID. Awkward features are homelab diagnostics, model-placement decisions, fresh-session conversational continuity, and backup coverage breadth. Demo-rich but not daily-use-complete areas are Agent Zero, staged self-service, voice, and JEV-like autonomy.

The five highest-value current workflows are: household inventory/expiry, recipe feasibility, daily health visibility, verified backup coverage, and bounded owner homelab/search research. The biggest week-one abandonment risks are incomplete telemetry, finance absence, stale/unclear automation state, and answers that are honest but too partial to help.

## 14. Roadmap matrix

| Domain | Classification |
|---|---|
| Chat | `DAILY USABLE` |
| Model routing | `DOGFOOD USABLE`; exact presets partly `UNVERIFIED` |
| Memory | `DOGFOOD USABLE`; latency `DEFERRED` |
| Grocy/household | `DAILY USABLE` for bounded reads |
| Recipes | `DOGFOOD USABLE`; owner draft creation and URL/paste ingestion staged with canonical verification |
| Finance | `DOGFOOD USABLE` for authorized CSV history; live balances/import `EXTERNAL-GATED` |
| Homelab read | `DOGFOOD USABLE` but incomplete composition |
| Homelab control | `OWNER-GATED` |
| Self-service workloads | `STAGED` |
| Web research | `DOGFOOD USABLE` |
| Browser interaction | `STAGED` / privileged paths `DEFERRED` |
| Voice | `STAGED` |
| Home Assistant | `DEFERRED` |
| Agent Zero | `DOGFOOD USABLE` owner-bounded |
| Automation/n8n | `ENGINEERING GREEN` for bounded contracts; arbitrary creation `DEFERRED` |
| Multi-user | `DOGFOOD USABLE` |
| Channels/shared collaboration | `DOGFOOD USABLE` with scope limits |
| Personal workspace/device integration | `PREPARATION ONLY` |
| JEV-style execution | `NOT STARTED` |
| Backup/recovery | `STAGED` same-site; whole-site `EXTERNAL-GATED` |

## 15. Drift/waste findings

1. `REPOSITORY VERIFIED` concern: many DOM and contract harnesses are valuable for authority/revocation/failure invariants, but they can become an end in themselves. Keep only tests tied to owner-visible risk.
2. `LIVE VERIFIED` concern: partial homelab telemetry currently produces honest but low-value answers; additional infrastructure without canonical telemetry would be theater.
3. `REPOSITORY VERIFIED` concern: public GitHub is 641 commits behind local HADES and infra has no upstream; external advisors cannot infer current truth from public source alone.
4. `GOOD COMPLEXITY`: subject isolation, explicit confirmation, canonical read-back, server-side grants, revocation, and bounded typed workflows are justified safety complexity.
5. `UNVERIFIED` drift risk: display names can imply finished model/voice products while physical endpoint/preset provenance remains partly unproven.

## 16. Current status reconciliation (2026-09-26)

This report began as a 2026-09-24 snapshot and its original recommendation list
is retained below as history. For current work, use
[`OWNER_AWAY_CAMPAIGN_STATE.md`](../OWNER_AWAY_CAMPAIGN_STATE.md),
`.owner-away-state.json`, and [`docs/current-blockers.md`](current-blockers.md).
The following differences are important when reading the older list:

- Production provenance is **still stale/contradicted**, not live-correct. The
  active Hermes overlay is `782709…`; the provenance endpoint still reports
  `1863ed…` and omits component hashes. Hermes and
  `hades-epsilon-source.service` were read-only confirmed active with zero
  restarts at 2026-09-26 18:39 UTC. No provenance refresh or deployment was
  performed.
- The persistent fresh-briefing/recap authenticated synthetic UI acceptance
  already passed on 2026-09-25; do not repeat absent regression.
- Hindsight's candidate latency budgets passed three independent synthetic
  pinned-runtime runs. Production latency/SLO and backlog cause remain open;
  production operation rows were not inspected or replayed.
- Point-in-time Proxmox CPU, memory, bounded disk-allocation, and uptime are
  already available in detailed owner status. Guest OS, major-service, and
  historical network/storage trend evidence remains missing. No broader host
  access was added.
- The local HADES and infrastructure worktrees contain preserved dirty work;
  the current revisions and precise next action are in the private campaign
  checkpoint. Do not treat the historical revision table below as current.

## 17. Historical recommended next actions (2026-09-24)

These recommendations are retained to explain the original handoff; use the
current status reconciliation above and the campaign checkpoint for today's
priority order.

1. Keep the refreshed deployed provenance in the normal deployment recorder path and verify it on each overlay restart. **Why:** this is now live-correct but must not regress. **Luna:** yes.
2. Preserve the already accepted point-in-time Proxmox CPU, memory, bounded disk-allocation, and uptime snapshot. The remaining gap is canonical guest OS / major-service visibility and historical network or storage trends. **Next:** check whether existing read-only Proxmox/Kuma data can answer a specific user question without widening access; otherwise state those fields as unknown. Do not treat a current snapshot as a root-cause diagnosis.
3. Deploy and verify the source repairs for cross-process Grocy recipe/list idempotency and cross-worker Health Watch confirmation on the authorized bounded routes. **Why:** two-process and route-level regressions now pass, but the active VM 802 overlay still has the old code. **Luna:** yes; preserve rollback and keep unrelated Task attention/Phase 3 routes out of scope.
4. **Repository and authenticated synthetic UI acceptance complete; production acceptance pending.** Owner CSV analysis distinguishes the earliest/latest transaction dates, calendar-month span, months with rows, partial edge months, latest row date, and export-file modification time. Month-to-date comparison uses the same calendar-day window in the prior month and explains category/description increases without claiming causation. A disposable authenticated Alpha/Beta UI run passes with synthetic data; production deployment/live Actual acceptance remains separately gated.
5. Re-run the fresh briefing/recap DOM test under a clean, low-load session and add a persistent continuity acceptance. **Luna:** yes.
6. **Repository result UX improved; live acceptance pending.** The fixed result path now names the HADES and infrastructure repository backup separately, shows each latest check and artifact date, and preserves last successful evidence across later stale/missing results from up to 100 completed runs. The current automated check covers only those two Git bundles; full service-volume backup coverage and missing custody remain explicit gaps. **Luna:** yes for current read sources; Scotty required for new custody.
7. Re-run 320x568, 390x844, desktop, stale-tab, double-submit, revocation, one-source failure, and mixed-task soak after the final deployment. **Luna:** yes.
8. Re-prove Hindsight latency with a bounded SLO and backlog observation. **Luna:** yes.
9. Keep off-site recovery explicitly deferred as requested; do not treat same-site Alexandra custody as disaster recovery. **Scotty required** only if this priority changes.
10. Keep JEV and unrestricted household automation deferred until the above owner workflows are useful and authorized. **Luna:** yes; no new framework required.

## 18. Proof appendix

**CLAIM:** HADES repository revision.  
**COMMAND:** `git -C $HADES_HOME/Hades rev-parse HEAD; git status --short --branch`  
**RESULT:** current repository HEAD `bcd81f435c4d8a6210802ffeb64c20a0ad3adbd7`; `main` is ahead of origin by 641. The current deployed product source is the same HEAD; the working tree contains only this report refresh and one local probe-helper change.
**CLASSIFICATION:** `REPOSITORY VERIFIED`

**CLAIM:** infra repository revision.  
**COMMAND:** `git -C $HADES_HOME/hades-infra rev-parse HEAD; git status --short --branch`  
**RESULT:** `bf648f52f5ab0e4da9ebd811f9ccc6866cf5341a`; clean `main`, no upstream.  
**CLASSIFICATION:** `REPOSITORY VERIFIED`

**CLAIM:** VM 802 runtime.  
**COMMAND:** `ssh scotty@<PRIVATE_LAN_ADDRESS> 'systemctl is-active hades-hermes.service; systemctl show hades-hermes.service -p WorkingDirectory'`  
**RESULT:** `active`; `$HADES_HOME/Hades-reconciled-b102dfd`.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** current mixed-user stale-tab/abandonment soak remains stable after the Phase 2 read repair.
**COMMAND:** `dom-rotating-multiplayer-soak.js` at `1440x900`, `390x844`, and `320x568`; the latest rerun was after deployment `bcd81f4`.
**RESULT:** all three runs returned `PASS`: owner Deep turn abandoned, owner stale-tab recovery completed, Household A received the bounded Grocy response without a write, Household B received server-side Agent Zero denial, and no Stop/composer residue or browser errors remained.
**CLASSIFICATION:** `LIVE VERIFIED` bounded multi-user viewport soak; the subsequent combined soak is recorded below.

**CLAIM:** Phase 2 typed summary reads are routed to their intended workflows.
**COMMAND:** fresh authenticated Owner, Household A, and Household B DOM prompts using `node scripts/dom-phase2-read-probe.js` at `390x844`, after deployment `bcd81f4`.
**RESULT:** owner low-summary response states the bounded Grocy read is enabled; owner weekly-summary response states it composes Grocy, Server Health Watch, and Backup Verification; owner backup discovery returns the HADES and infrastructure Backup Checks; Household A receives the typed weekly status; Household A/B receive explicit no-shared-resource responses for unshared resources. No schedule was created by this read-only probe.
**CLASSIFICATION:** `LIVE VERIFIED` routing/read behavior; partial failure and complete household-sharing semantics remain `UNVERIFIED`.

**CLAIM:** Phase 2 read probes settle across Owner, Household A, and Household B without cross-user reuse.
**COMMAND:** `node scripts/dom-phase2-read-probe.js` at `390x844`, with the latest product deployment `bcd81f4`.
**RESULT:** all 9 identity/workflow turns settled. Owner saw Backup Check, Low Grocery Summary, and Weekly Household Summary status. Household A saw the shared Weekly Summary and explicit no-shared responses for Backup/Low Inventory. Household B saw explicit no-shared responses for all three. Response digests were distinct where authorization differed; no production schedule was created or changed.
**CLASSIFICATION:** `LIVE VERIFIED` bounded DOM authorization/read matrix; partial failure and full weekly recipient composition remain `UNVERIFIED`.

**CLAIM:** approved Backup, Low Inventory, and Weekly workflows execute through the owner-facing product and reconcile canonical n8n results.
**COMMAND:** `HADES_PHASE2_EXECUTE=1 node scripts/dom-phase2-read-probe.js` after deploying the Phase 2 workflow repair; read-only n8n execution listing/detail for the resulting workflow IDs.
**RESULT:** Owner preview/confirmation completed for Weekly, Low Grocery, and Backup. Visible results were respectively `Groceries: current Low Grocery result is available; Servers: up; Backups: healthy`, `Current result: ready; current Grocy stock read`, and `Current result: healthy; checksum matched and git bundle verified`. Canonical n8n executions were successful at approximately 07:22Z; Weekly carried Grocy `READY/CURRENT`, Backup `HEALTHY/CURRENT`, and Server Health `UP/CURRENT`; Low carried Grocy `READY/CURRENT`; Backup carried `HEALTHY/CURRENT`. No external notification or resource mutation occurred.
**CLASSIFICATION:** `LIVE VERIFIED` approved happy-path execution/freshness/provenance; controlled outage and partial-failure behavior remain `UNVERIFIED`.

**CLAIM:** Weekly server-health omission defect is repaired.
**COMMAND:** live execution detail before and after the fixed graph update; `test-epsilon-phase2-contracts.sh`.
**RESULT:** pre-repair Weekly execution merged Grocy and Backup but health was only `{status:true}` and had no typed state. The fixed graph adds `Bounded server health result projection`; the fresh execution contains `server-health-watch`, `hades_state: UP`, `hades_reason: canonical HADES health status`, and `freshness: CURRENT`. The contract now asserts the projection and connection.
**CLASSIFICATION:** `LIVE VERIFIED` repair and regression evidence.

**CLAIM:** shared Weekly result history is visible only to an authorized recipient and disappears after revocation.
**COMMAND:** `HADES_PHASE2_HISTORY_ONLY=1 node scripts/dom-phase2-read-probe.js`; owner revocation and re-share through `HADES_PHASE2_REVOKE_ONLY=1` with the authenticated DOM probe.
**RESULT:** before revocation, Owner and Household A both saw the bounded latest result (`Groceries: current Low Grocery result is available; Servers: up; Backups: healthy`); Household B was denied. Owner revoked Weekly sharing from Household A; fresh A and B probes both returned `No shared Weekly Household Summary is available...`. Sharing was then restored to preserve the pre-test user state. No source or resource mutation occurred.
**CLASSIFICATION:** `LIVE VERIFIED` shared result/revocation behavior; other resource families remain unshared in the current state.

**CLAIM:** latest-history language no longer falls into staged Phase 3 metadata.
**COMMAND:** fresh authenticated DOM prompt `show the latest weekly household summary` after deployment `bcd81f4`.
**RESULT:** Owner and authorized Household A received the bounded Weekly result; Household B received the server-side no-shared response. The prior staged-metadata response was a real routing defect and is repaired.
**CLASSIFICATION:** `LIVE VERIFIED` routing repair.

**CLAIM:** deployed overlay identity.  
**COMMAND:** live provenance endpoint plus remote `sha256sum` of overlay and reconciled `sitecustomize.py`.  
**RESULT:** live overlay and finance asset were copied to VM 802 and match the deployed source artifacts; provenance reports HADES `bcd81f4...`, infra `bf648f5...`, overlay `1863ed16...`, and manifest `811807...`, generated `2026-09-24T07:54:33Z`.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** homelab owner read uses bounded live VM runtime evidence.  
**COMMAND:** fresh authenticated owner DOM prompts for full homelab status and network diagnosis; supplemental Proxmox `cluster/resources?type=vm` GET through the existing adapter.  
**RESULT:** owner-visible response listed Alexandra/Erebus and running VM 801 `hades-operator`, VM 802 `hades-core`, and VM 852 with current CPU, memory, and bounded disk allocation values; OS, major services, GPU, and network trends remained explicitly unknown. No control operation or mutation was called.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** household private-domain isolation.  
**COMMAND:** fresh authenticated Household A and Household B DOM sessions at `390x844`; finance prompt for A and Scotty-private-memory prompt for B.  
**RESULT:** A received owner-only finance denial; B received private-memory denial; neither request invoked a private read or changed state.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** original recipe-chat failure corpus is repaired.  
**COMMAND:** five fresh authenticated DOM sessions using the original prompts: makeable recipes, not-makeable recipes, saved recipes, `what recipes do we have?`, and cooking recipes.  
**RESULT:** all five returned canonical Grocy recipe/stock output; the live catalog contained three recipes; no stock or shopping-list write occurred.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** final exhaustive owner corpus settled after the latest repairs.
**COMMAND:** `HADES_DOM_FRESH_EACH=1 HADES_DOM_TURN_TIMEOUT_MS=45000 HADES_DOM_REPORT=/tmp/hades-exhaustive-final-authorized.json node scripts/dom-exhaustive-owner-dogfood.js`.
**RESULT:** `COLLECTED`, 15/15 seed turns. Finance historical prompts used the authorized CSV; current-balance prompts remained bounded refusals. Homelab used live Proxmox/NetBox/Kuma. A fresh follow-up single-submit spaghetti proof completed with canonical recipe/list confirmation and no Stop state.
**CLASSIFICATION:** `LIVE VERIFIED` evidence collection; overall product closure remains `UNVERIFIED` pending remaining Phase 2 acceptance gates.

**CLAIM:** authorized finance CSV is readable by live Hermes.
**COMMAND:** protected VM runtime file check plus fresh owner DOM finance prompts.
**RESULT:** `/var/lib/hades-runtime/finance/bk_download.csv` is readable by `hades-runtime`; 539 usable rows, date range 2026-01-02 through 2026-09-10, 2 pending. No raw rows or private amounts are reproduced here.
**CLASSIFICATION:** `LIVE VERIFIED` owner-only read-only source

**CLAIM:** end users are not required to know an Actual Budget account ID.
**COMMAND:** fresh authenticated owner DOM prompts `What are actual budget account IDs?` and `import this` after the finance overlay deployment.
**RESULT:** HADES explained that the statement has no Actual IDs, that no verified live Actual account catalog is configured, and that no import occurred. The `import this` follow-up is now routed to the authorized local statement path rather than the old generic account-ID instruction.
**CLASSIFICATION:** `LIVE VERIFIED` UX correction.

**CLAIM:** CSV upload UX no longer requires the user to know an internal account ID.
**COMMAND:** `bash scripts/test-finance-webui-upload-contract.sh`; live attached `bk_download.csv` DOM inspection.
**RESULT:** contextual `Review CSV` appears after attachment; review text accepts an optional account name and says HADES resolves internal IDs. No global finance control is installed.
**CLASSIFICATION:** `LIVE VERIFIED` / `REPOSITORY VERIFIED`

**CLAIM:** owner-authorized spaghetti canonical state exists.
**COMMAND:** live Grocy reads for products, `HADES Owner Spaghetti Draft`, recipe positions, and shopping list after the authorized DOM action.
**RESULT:** recipe ID 9 with five ingredient positions; missing product rows and shopping-list rows were read back. Duplicate shopping rows created during the ambiguous retry were removed; no stock was fabricated. A fresh single-submit DOM turn returned the verified canonical result with no Stop state.
**CLASSIFICATION:** `LIVE VERIFIED` canonical state and turn closure

**CLAIM:** full homelab telemetry inputs are live.
**COMMAND:** bounded homelab adapter read with configured Proxmox GET endpoints, NetBox read endpoint, and Uptime Kuma status page; fresh owner DOM homelab/network prompts.
**RESULT:** source counts include Proxmox runtime, NetBox inventory, and Kuma monitor rows; Proxmox currently reports Alexandra/Erebus online and Kuma reports `service-netbox` down. Guest OS, major services, storage trends, GPU load, and network trends remain unknown.
**CLASSIFICATION:** `LIVE VERIFIED` partial telemetry

**CLAIM:** off-site recovery status.
**COMMAND:** owner instruction in current task scope.
**RESULT:** off-site custody was intentionally skipped and is not represented as available recovery evidence.
**CLASSIFICATION:** `DEFERRED`

**CLAIM:** receipt-photo ingestion remains review-gated and non-silent.
**COMMAND:** authenticated `scripts/dom-receipt-rotation.js` with partial and rotated synthetic receipt photos; receipt/OCR contracts.
**RESULT:** both photos rendered OCR review state, one exact milk match and unresolved/uncertain lines, and visible confirmation controls; no pantry write was performed. `PASS` is used here only for the harness result supported by this evidence.
**CLASSIFICATION:** `LIVE VERIFIED` / `REPOSITORY VERIFIED`

**CLAIM:** bounded completion-abort recovery.
**COMMAND:** `scripts/dom-dependency-failure.js` with one aborted completion and recovery prompt.
**RESULT:** the aborted request rendered `Failed to fetch` and cleared the composer; recovery returned a live Tartarus response, but the Stop control was still visible at the harness's 15-second cutoff.
**CLASSIFICATION:** `LIVE VERIFIED` partial; `BROKEN` recovery-liveness timing at the current cutoff

**CLAIM:** Open WebUI health and owner surface.  
**COMMAND:** authenticated browser navigation and DOM prompts against the production HADES URL.  
**RESULT:** login/session established; 15 seed turns collected; recipe, expiry, restock, briefing, and failure-recovery responses visible.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Hermes version/service.  
**COMMAND:** systemd unit executable and runtime health.  
**RESULT:** Hermes `0.21.2`; service active.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Hindsight health.  
**COMMAND:** VM 802 health endpoint.  
**RESULT:** healthy/database connected; fresh-memory proof exists with delayed indexing.  
**CLASSIFICATION:** `LIVE VERIFIED` health; latency `DEFERRED`

**CLAIM:** fresh owner memory survives a genuinely new conversation.  
**COMMAND:** `HADES_HINDSIGHT_MARKER=<harmless synthetic marker> HADES_EPSILON_DOM_WAIT_MS=120000 node scripts/dom-hindsight-alpha.js` after the persistent Hindsight route/overlay repair.  
**RESULT:** `status=PASS`, `fresh_conversation=true`, and the new marker was
present in the natural recall response. The Hindsight container reported
healthy/database connected; no other bank was queried.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** affected multi-user authorization discovery remains intact after the
memory repair.  
**COMMAND:** `HADES_EPSILON_DOM_DISCOVERY_ONLY=1 node scripts/dom-epsilon-phase2-staged.js`.  
**RESULT:** 12/12 sessions settled across Owner, Household A, and Household B
at desktop, tablet, 390x844, and 320x568; no production enablement occurred.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Grocy canonical path.  
**COMMAND:** live Grocy API plus owner DOM recipe/stock/expiry reads.  
**RESULT:** three live recipes and current stock/expiry data observed; owner responses cite canonical reads and no-write behavior.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** SearXNG path.  
**COMMAND:** bounded loopback HTTP probe and web-failure contract.  
**RESULT:** service reachable; failure boundary contract is green in repository evidence.  
**CLASSIFICATION:** `LIVE VERIFIED` path / `REPOSITORY VERIFIED` failure contract

**CLAIM:** LLDAP/auth state.  
**COMMAND:** protected LDAP auth smoke for Owner/A/B; emit only status, subject, and role.  
**RESULT:** all HTTP 200; distinct subjects `45ed2520...`, `d5e8a4f3...`, `53c31d45...`; all role `user`.  
**CLASSIFICATION:** `LIVE VERIFIED`; group display `UNVERIFIED`

**CLAIM:** current inference endpoints/models.  
**COMMAND:** bounded `/api/tags`/`/v1/models` probes on ports `11435`, `11437`, `11434`.  
**RESULT:** Hermes Compute qwen3:8b; Tartarus qwen3.6:35b; Hypnos gemma4:e4b and embedding model.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Proxmox/topology reachability.  
**COMMAND:** bounded ICMP/TCP checks for listed nodes and configured VM 802 path.  
**RESULT:** VM 802 and listed inference/storage endpoints reachable where stated; reachability does not prove workload health.  
**CLASSIFICATION:** `LIVE VERIFIED` reachability only

**CLAIM:** Alexandra ZFS health.  
**COMMAND:** bounded noninteractive SSH read attempt for `zpool status -x`.  
**RESULT:** host reachable but identity rejected.  
**CLASSIFICATION:** `EXTERNAL-GATED` / `UNVERIFIED`

**CLAIM:** Agent Zero state.  
**COMMAND:** VM 802 container inventory and owner/household policy paths.  
**RESULT:** container live; household delegation denied; owner route remains bounded.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** voice service state.  
**COMMAND:** bounded HTTP probe to Hermes Compute `:8766`.  
**RESULT:** live HTTP listener returned 404 at root; exact STT/TTS readiness not proven.  
**CLASSIFICATION:** `LIVE VERIFIED` listener / `UNVERIFIED` end-to-end

**CLAIM:** n8n state.  
**COMMAND:** VM 802 container health and `/healthz`.  
**RESULT:** container active; health response `status=ok`; arbitrary workflow creation not enabled.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** Home Assistant state.  
**COMMAND:** current live owner-facing capability/configuration inspection.  
**RESULT:** no authorized owner-facing action path established.  
**CLASSIFICATION:** `DEFERRED` / `OWNER-GATED`

**CLAIM:** canonical owner dogfood.  
**COMMAND:** `HADES_DOM_FRESH_EACH=1 HADES_DOM_TURN_TIMEOUT_MS=45000 node scripts/dom-exhaustive-owner-dogfood.js` with protected owner auth and report `/tmp/hades-exhaustive-final-authorized.json`.  
**RESULT:** 15/15 seed turns collected; canonical Grocy routes, authorized finance CSV analysis, explicit finance/telemetry boundaries, and mobile expiry route at `390x844` observed. A separate clean spaghetti turn completed with no Stop state.  
**CLASSIFICATION:** `LIVE VERIFIED` evidence collection; overall product closure `UNVERIFIED`

**CLAIM:** failure recovery.  
**COMMAND:** bounded authenticated DOM transport-abort fixture.  
**RESULT:** visible `Failed to fetch`, no stale Stop state, recovery response returned.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** fresh briefing recap route.  
**COMMAND:** clean authenticated DOM session, new chat, prompt `What did we learn from my morning briefing, and what needs attention first?`  
**RESULT:** returned `HADES morning briefing refresh (bounded live sources)` with infrastructure, backup, household, expiry, and finance-boundary sections; no model-generated stale-context claim.  
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** urgent briefing follow-up remains usable without relying on a model turn.
**COMMAND:** fresh authenticated owner DOM session; persistent `Give me my HADES morning briefing.` followed by `What should I handle first, and why?` after the bounded 8-second assistant-settlement window.
**RESULT:** both turns returned; the follow-up returned a live briefing refresh with infrastructure, backup, household, expiry, finance, and priority context; no Stop state remained. Immediate submission during the five-second UI settlement window is intentionally guarded with composer-preservation feedback.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** sustained capstone owner session.
**COMMAND:** persistent authenticated DOM sequence covering briefing, follow-up, homelab, network, recipes, expiry, grocery mutation, backup, finance, restock, spending, task inspection, mobile continuation, dependency abort/recovery, and fresh-chat continuation.
**RESULT:** the current websocket-aware persistent owner corpus collected all 15/15 seed workflows in one session: recipes, expiry, canonical spaghetti/list action, homelab, network, model placement, backup coverage, utilities, dining, subscriptions, weekend affordability, rent goal, restock, spending-cut analysis, and morning briefing. Every seed returned a useful result; the longest was about 3 seconds before the bounded 8-second UI settlement. The same run then completed a briefing follow-up, a correction/change-of-mind turn, 390x844 mobile continuation, and fresh-chat briefing recap. Separate live abort/re-entry and multi-user fixtures pass. The later combined soak adds the stale-tab, double-submit, multi-viewport, and Owner/A/B coverage; live dependency outage and full weekly partial-failure execution remain open.
**CLASSIFICATION:** `LIVE VERIFIED` 15/15 persistent seed corpus; later combined soak is separately verified below.

**CLAIM:** short persistent owner sequence remains stable after the capstone probe.
**COMMAND:** fresh authenticated owner DOM session; sequential `Give me my HADES morning briefing.`, `What should I handle first, and why?`, and `What food is going to expire in the next 7 days?`, with an 8-second settlement window after each turn.
**RESULT:** all three turns returned useful live answers; each ended with an empty composer, no Stop control, and no busy/failure notice. Elapsed times were approximately 9.7s, 9.1s, and 8.6s including the settlement window.
**CLASSIFICATION:** `LIVE VERIFIED` bounded persistent sequence; broader mixed capstone remains `UNVERIFIED`

**CLAIM:** latest Phase 2 deployment did not regress the complete persistent owner seed corpus.
**COMMAND:** `HADES_DOM_FRESH_EACH=0 HADES_DOM_TURN_TIMEOUT_MS=60000 HADES_DOM_REPORT=/tmp/hades-exhaustive-persistent-post-phase2.json node scripts/dom-exhaustive-owner-dogfood.js`.
**RESULT:** `COLLECTED`, 15/15 turns in one authenticated session: recipes, expiry, spaghetti/list action, homelab, network, model placement, backup, utilities, dining, subscriptions, safe-spend refusal, lease-goal refusal, restock, spending-cut analysis, and morning briefing. No timeout or dependency-error marker appeared in the bounded result set.
**CLASSIFICATION:** `LIVE VERIFIED` persistent seed regression; broader mixed capstone remains `UNVERIFIED`.

**CLAIM:** finance shortcut and long-context rent continuity.
**COMMAND:** deployed owner DOM corpus after the bounded finance route was moved ahead of long-history intent reconstruction; persistent weekend-affordability followed by lease-goal prompts.
**RESULT:** both turns returned in about 1.4 seconds before UI settlement; weekend refusal correctly cites missing balances/future obligations, while lease refusal separately cites missing current balance, lease target, remaining lease amount, and future paychecks. The finance shortcut explicitly excludes compound briefing/homelab/recipe/restock prompts, which continue through their composed routes.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** natural-language correction after a finance turn.
**COMMAND:** persistent owner DOM sequence: utilities question followed by `Actually, forget the spending advice for now. Just give me the grocery items that need attention.`
**RESULT:** first turn returned owner-only CSV analysis; the correction returned canonical Grocy stock (`HADES Synthetic Milk`, 2 units) rather than repeating the finance answer. The deployed correction-precedence repair is active.
**CLASSIFICATION:** `LIVE VERIFIED`

**CLAIM:** targeted contracts.  
**COMMAND:** `test-turn-liveness-contract.sh`, `test-task-store.sh`, `test-health-watch-contract.sh`, `test-web-failure-boundary.sh`, `test-epsilon-workflow-contract.sh`, `test-homelab-readonly-adapter.sh`.  
**RESULT:** all reported successful contract assertions.  
**CLASSIFICATION:** `REPOSITORY VERIFIED` (contract evidence, not a blanket production declaration)

**CLAIM:** live Health Watch sharing, household authority, and revocation.
**COMMAND:** authenticated owner/Household A DOM turns plus canonical SQLite state read-back; owner share/revoke, household inventory/run, and duplicate reconciliation fixtures.
**RESULT:** Household A could see the shared `HADES Core Watch` but `run HADES Core check` returned `This shared health watch is view-only for you; I did not change or run it.` After owner revocation, Household A saw no authorized watch. Canonical state ended with one enabled `HADES Core Watch` and zero shared subjects. The deployed fix also routes named health-watch actions ahead of Phase 3 staged automation.
**CLASSIFICATION:** `LIVE VERIFIED` bounded authority/revocation; bare cross-worker `yes` confirmation remains `UNVERIFIED`

**CLAIM:** mixed multi-user persistent soak across required viewports.
**COMMAND:** `dom-rotating-multiplayer-soak.js` with concurrent owner abandonment and Owner-tab recovery at 1440x900, 390x844, and 320x568.
**RESULT:** all three viewport runs returned `PASS`: owner generation was abandoned, the second owner tab recovered with `hello`, Household A received a safe canonical Grocy no-match response without a write, Household B received server-side Agent Zero denial, and no Stop/composer residue or browser errors remained.
**CLASSIFICATION:** `LIVE VERIFIED` three viewport runs; the combined all-fixture result is recorded separately below.

**CLAIM:** recipe availability variants preserve canonical routing across all three identities.
**COMMAND:** `HADES_PHASE2_RECIPE_ONLY=1 node scripts/dom-phase2-read-probe.js` after deployment `bcd81f4`.
**RESULT:** Owner, Household A, and Household B each received the same canonical Grocy recipe/stock answer for three phrasings: `List my recipes ... without buying anything`, `List my recipes ... right now`, and `Which recipes can we make right now?`; no write occurred.
**CLASSIFICATION:** `LIVE VERIFIED` read routing and household-safe canonical data

**CLAIM:** combined Phase 2 persistent DOM soak settles current responses without cross-user reuse.
**COMMAND:** `node scripts/dom-phase2-combined-soak.js` after deployment `bcd81f4`.
**RESULT:** `PASS`; 20/20 turns settled across Owner, Household A, and Household B at desktop 1440x900, 390x844, and 320x568. Owner covered briefing/follow-up, homelab, network, recipe availability, expiry, restock, subscriptions, backup read/double-submit, stale-tab abandonment/recovery; Household A received the shared Weekly result; Household B received denial. The recipe response was canonical Grocy output after the stale-history routing repair.
**CLASSIFICATION:** `LIVE VERIFIED` combined soak; live dependency-outage and full weekly partial-failure execution remain `UNVERIFIED`

**CLAIM:** stale homelab context no longer steals a current recipe request.
**COMMAND:** fresh authenticated Owner recipe prompt in the combined soak, plus repository inspection of `hermes/sitecustomize.py` after deployment `bcd81f4`.
**RESULT:** the pre-fix combined turn returned a generic bounded-server response despite isolated recipe probes succeeding. The fix routes current-turn text, rather than stale `_hades_intent_text`, through homelab control/provisioning guards. Post-fix the same combined recipe turn returned the canonical saved Grocy recipe list and makeability state.
**CLASSIFICATION:** `LIVE VERIFIED` defect and repair

**CLAIM:** weekly composition preserves healthy sources when Grocy fails in a bounded fixture.
**COMMAND:** `bash scripts/test-epsilon-phase2-contracts.sh` partial-composition assertion using a synthetic Grocy reader exception.
**RESULT:** output preserves `Backups: healthy`, `Servers: up`, and `Unavailable this week: Groceries.` No production source was disabled.
**CLASSIFICATION:** `REPOSITORY VERIFIED` bounded partial-failure contract; live outage behavior remains `UNVERIFIED`

**CLAIM:** typed Epsilon failure fixtures do not become false success.
**COMMAND:** `bash scripts/test-epsilon-phase2-contracts.sh` plus the disposable source-projection fixture invoking `InventoryObservation`/rendering, `BackupVerificationService.reconcile_execution`, `compose_summary`, and the fixed `integrations/epsilon-source/server.py` inventory projection with a monkeypatched source failure.
**RESULT:** the durable contract now covers `SOURCE_UNAVAILABLE`, `FAILED`, `MISSING`, `STALE`, `UNKNOWN`, and `HEALTHY` typed backup states, preserves `last` state semantics, and checks that Grocy unavailable renders `no stock conclusion`. The fixture also preserved `Backups: healthy` and `Servers: up` while emitting `Unavailable this week: Groceries.`; the source adapter projected `SOURCE_UNAVAILABLE`. No production endpoint or n8n workflow was modified.
**CLASSIFICATION:** `REPOSITORY VERIFIED` bounded failure fixture matrix; live dependency outage remains `UNVERIFIED`

**CLAIM:** bounded dependency failure and re-entry.
**COMMAND:** authenticated owner `dom-dependency-failure.js` with protected credentials and bounded chat abort.
**RESULT:** visible `Failed to fetch`, empty composer, no Stop state, and a genuinely new recovery response `Hello! How can I assist you today?`; the corrected fixture required New Chat to clear prior assistant nodes and reported `new_response: true`; no browser errors.
**CLASSIFICATION:** `LIVE VERIFIED` corrected abort/re-entry evidence; the earlier stale-node false green is retained as a harness defect and is not counted as evidence.

**CLAIM:** provenance record contents at the 07:54Z observation.  
**COMMAND:** live `/v1/epsilon/provenance` after deployment recorder refresh.  
**RESULT:** HADES `bcd81f4...`, infra `bf648f52...`, overlay `1863ed16...`, manifest `811807...`, generated `2026-09-24T07:54:33Z`; Hermes service was active with `NRestarts=0`. The later read-only service-path audit found the effective overlay hash was `2157f732...` after the 15:07Z restart.
**CLASSIFICATION:** historical record observation; current provenance `STALE / CONTRADICTED`

**CLAIM:** current Phase 2 source/read paths still reconcile after the combined soak and fixture work.
**COMMAND:** `node scripts/dom-phase2-read-probe.js` at 390x844; authenticated owner/Household A/Household B read-only probe; live `/v1/epsilon/inventory` and `/v1/epsilon/backup/hades` through the deployed host bridge.
**RESULT:** Owner sees enabled Backup, Low Grocery, and Weekly Summary status; Household A sees only the shared Weekly Summary; Household B receives no shared Weekly Summary; unshared Backup/Low Inventory remain denied. Live Grocy source is `READY/CURRENT`; HADES backup is `HEALTHY`, checksum matched, and git bundle verified. No schedule or resource was changed.
**CLASSIFICATION:** `LIVE VERIFIED` current routing, authorization, freshness, and canonical source state

### Hindsight follow-up (2026-09-25)

**CLAIM:** fresh Alpha memory recall remains reliable after a new retain.  
**COMMAND:** one authenticated owner DOM probe retained a harmless synthetic fact, opened a genuinely new conversation, and asked a natural recall question.  
**RESULT:** `FAIL`: recall returned a different older synthetic Alpha marker rather than the just-retained fact. The test took 70.4 seconds; recall started about 30.8 seconds after retain settled. This is a same-owner freshness failure, not evidence of cross-user disclosure. No further production Hindsight writes, retries, or deletes were attempted.  
**CLASSIFICATION:** `LIVE VERIFIED` reliability defect; Hindsight remains open P2.

**CLAIM:** current asynchronous Hindsight backlog.  
**COMMAND:** read-only aggregate of the pinned API stats endpoint across 13 banks; no operation details queried.  
**RESULT:** 3 pending operations, 470 failed operations, 38 pending consolidations, and 1,118 failed consolidations. These current counts supersede earlier lower consolidation counts; failed operation stats may include parent/child batch accounting. No retries or replay were attempted.  
**CLASSIFICATION:** `LIVE VERIFIED` aggregate backlog; cause and safe recovery remain unverified.


### Backup Check per-repository evidence (2026-09-25)

The fixed Phase 3 backup source already returns separate HADES and infrastructure
repository observations, including artifact modification time and check time.
The result route now preserves the latest successful check per target across
up to 100 completed runs and renders that alongside the current target state.
It recognizes natural questions such as “When were our backups last
verified?” and “Are my backups up to date?” only as read-only result queries.
The result is explicitly labeled “Repository backups” so it cannot imply
Open WebUI, LLDAP, Hindsight, Grocy, Hermes profile, Agent Zero, or SearXNG
state is backed up.

`test-phase3-runner.sh` proves a healthy result followed by stale/missing
results retains both targets’ last-good artifact dates;
`test-phase3-result-client.sh` proves exact target labels, state and timestamp
rendering, natural-language intents, bounded timestamps, and redaction of
unknown target IDs/private strings. `test-epsilon-phase2-contracts.sh` verifies
the fixed source returns both per-repository observations. Phase 3 requester,
runner, load/idempotency, and Epsilon contracts pass. This is repository
evidence only; no production changes or authenticated owner acceptance were
performed. Full stateful service backups, encrypted off-site custody, and
complete restore remain separate gates.

### Hindsight post-repair live smoke and Backup Check route (2026-09-25)

After composing the typo/correction-aware direct-memory fix into the exact
active generated overlay and restarting Hermes with a saved rollback copy, an
authenticated owner smoke retained a harmless marker and recalled it in a new
conversation. It passed in 66.3 seconds total, with 33.1 seconds from retain to
successful recall. This was a fresh-fact smoke, not the exact typo/correction
production scenario; the pinned synthetic runtime remains the evidence for
that path, and a latency SLO is still unproven. The active overlay SHA-256 is
`0c1abb2d3bb44bbb643e5c130ac5fd4afa248666d2f911388fba1e6ce71af6c3` and its
rollback copy is `$HADES_HOME/generated-full/config/overlay/sitecustomize.py.pre-hindsight-330356e`.

The backup results source now retains and renders per-repository last-good
artifact/check evidence, and the Hermes prefilter now admits ordinary backup
freshness questions through the exact read-only result intent check. Focused
runner/result/request, authenticated-identity, owner-surface, capability,
Epsilon and backup-document contracts pass. This is source evidence only for
the backup UI; the production update and authenticated owner acceptance remain
pending. Current public refs were rechecked: `origin/main` remains
`a654675d`, `public-release-candidate` remains `fd0f4e5`, and
`v0.1.0-preview.10` remains `07a058c`.

### Named saved-recipe “make it again” household question (2026-09-25)

An authenticated disposable Beta UI flow now accepts “Can I make Synthetic
Pancakes again?” as a canonical saved-recipe availability read. The answer uses
current Grocy recipe positions and stock, reports the exact egg shortage, and
states that nothing changed. The end-to-end household harness passed after the
request audit was updated for the additional recipe/unit-conversion reads; the
same run retained its existing canonical recipe feasibility, low-spend meal,
shortage-list write/read-back, retry, outage-honesty, and actor-audit checks.
The acceptance report is `/tmp/hades-grocy-household-ui-3515155.json` (0600).
This is synthetic disposable evidence only; no production Grocy state or
service was queried or changed. The phrase “that chicken thing” still needs a
saved-recipe reference to resolve; unresolved names are designed to ask what
the user calls the saved recipe without changing state.

A separate exploratory sequence inserted the vague “that chicken thing” prompt
before later recipe turns. Although the clarification was rendered, the
following low-spend question did not settle through the direct route within the
UI harness window and reached the deliberately unavailable model endpoint. That
sequence is not counted as a pass; the named-recipe end-to-end run above is the
accepted result. Investigate the multi-turn interaction before claiming the
full Grandma reference workflow.

### Grandma recipe reference resolved through canonical ingredients (2026-09-25)

The earlier multi-turn limitation is now closed for the representative
“Can I make that chicken thing again?” workflow. The deterministic recipe read
matches meaningful words against saved recipe names and their canonical
Grocy ingredients, and proceeds only when exactly one saved recipe matches.
The synthetic household fixture contains one chicken recipe, “Lemon Chicken.”
The authenticated Beta UI returned “Not quite yet: Lemon Chicken still needs
chicken (1 more),” based on canonical stock, with no state change. The prompt is
run after the existing low-spend workflow, which still passes; the full
`test-grocy-authenticated-household-ui.sh` audit passed, including the exact
recipe, ambiguity, mutation, outage, and actor checks. Report:
`/tmp/hades-grocy-household-ui-3522641.json` (0600). No production data or
service was queried or changed. If multiple saved recipes match the ingredient
word, the handler asks for the saved recipe name instead of guessing.

### Broad computer status now includes backup freshness (2026-09-25)

The owner-only read-only homelab summary now composes requester-scoped Phase 2
backup freshness alongside Proxmox runtime, Uptime Kuma observations, and
explicit unknowns. Natural broad wording including “Is everything okay with
the servers?” and “Are all the computers okay?” takes the detailed path; the
latter previously missed because the classifier did not accept “all the
computers.” A synthetic authenticated Alpha UI run returned the healthy HADES
repository backup and last successful check time in both answers, while
preserving Search failure, stale Jellyfin observation, Minecraft probe limits,
and unverified inference-worker health. The focused backup contract confirms
the freshness lookup remains requester-scoped and read-only; the UI uses an
unreachable model endpoint to ensure the answer is deterministic. The full
Alpha/Beta/Gamma authenticated acceptance passed. Report:
`/tmp/hades-task-attention-backup-compose.json` (0600). Production untouched;
no household or production access was added.

### Authenticated source acceptance rerun (2026-09-26)

The repository-source authenticated confirmation-isolation harness passed
twice consecutively after one initial run timed out on the same-chat decline.
Across the passing runs, Alpha received a Backup Check confirmation in chat A;
a bare “Yes” in distinct chat B returned the chat-mismatch response and left
the lifecycle database SHA-256 unchanged; after reloading chat A, “No” cleared
only that pending action. Neither user turn invoked the deliberately
unreachable model endpoint. Containers and volumes were removed after each
run. The initial failure is retained as a timing-sensitive harness/runtime
observation rather than omitted. Reports:
`/tmp/hades-phase2-confirmation-isolation-3695855.json` and
`/tmp/hades-phase2-confirmation-isolation-3700640.json` (0600). This is
repository-source synthetic evidence; production still runs a stale,
contradicted overlay and was not changed.

The authenticated backup-freshness UI harness also passed against synthetic
canonical state. “Do we have a recent backup?” returned the healthy HADES
repository status and last-successful/latest-check timestamps; the answer was
persisted in chat, the Hermes model was not called, and the state database
SHA-256 remained identical before and after the turn. Its disposable container
and volume were removed. Report:
`/tmp/hades-backup-freshness-ui-3707020.json` (0600). This closes the local
authenticated wording/read-only contract, not production freshness or an
off-host-backup claim.

### Confirmation acceptance harness root cause (2026-09-26)

The earlier non-settling “No” run was a browser submission failure, not a HADES
confirmation-key failure. In the failing run, Hermes logged the initial request
and the separate-chat “Yes” request but received no third `/api/chat/completions`
request. Playwright's send-button click trace showed a transient informational
overlay intercepting the pointer. A diagnostic-only copy of the repository
overlay hashed the actual Hermes `AIAgent.session_id`: the same chat derived
the same server session after reload, while the second chat derived a
different session. Raw session IDs were not retained.

The authenticated harness now waits for an idle composer, submits through
Enter, and requires an Open WebUI chat-completion request before judging the
HADES response. It includes bounded UI diagnostics when submission or response
settlement fails. The exact two-chat acceptance passed first with the temporary
session-hash trace and again with the unmodified repository overlay. A final
same-chat decline cleared only its pending action; cross-chat “Yes” preserved
the lifecycle DB hash; no model calls occurred. Reports:
`/tmp/hades-phase2-confirmation-isolation-3775335.json` and
`/tmp/hades-phase2-confirmation-isolation-3778979.json` (0600); redacted runtime
identity result `/tmp/hades-confirmation-session-identity-20260926.json` (0600).
Production was not contacted or changed. The earlier failure remains recorded
as a harness/UI timing observation, not as a confirmed product regression.

The same authenticated freshness fixture was then expanded to include a
healthy HADES repository record and a stale infrastructure repository record
with an earlier last-good time. The UI correctly showed the HADES record as
healthy, identified the infrastructure record as stale and needing attention,
and preserved its last successful check separately from the latest stale
check. Chat persistence passed, no model was called, the state database hash
was unchanged, and the disposable runtime was cleaned. The harness now asserts
both records and both timestamps. Report:
`/tmp/hades-backup-freshness-ui-3724130.json` (0600). This is synthetic
authenticated acceptance; live source outage remains untested.

### Authenticated dependency failure and recovery (2026-09-26)

A disposable Open WebUI 0.11.1 instance authenticated synthetic Alpha against a
local deterministic OpenAI-compatible responder. Playwright aborted the first
`/api/chat/completions` request and observed Open WebUI's visible “Failed to
fetch” state. It then created a fresh chat and verified a second request
reached the local responder and rendered “Synthetic recovery succeeded.” The
report confirms the first request failed with `net::ERR_FAILED`, the second
request was submitted, the composer settled, and no browser page errors
occurred. The fixture used loopback-only WebUI exposure, synthetic credentials,
a temporary Docker volume, and a local-only model responder. Its container and
volume were removed after the run. Report:
`/tmp/hades-dependency-failure-ui-3804413.json` (0600).

The run exposed two harness assumptions: this WebUI build's welcome modal
intercepts navigation controls until dismissed, and the harness's error path
could leave Playwright/Chromium alive, preventing fixture cleanup. The harness
now uses the authenticated API token cookie, dismisses the welcome modal,
asserts that recovery submits a second actual chat request, and exits on
Playwright errors so shell cleanup runs. The acceptance runner also rejects
occupied ports and refuses to use any production endpoint. Production was not
contacted or changed.

### Exact backup-history question (2026-09-26)

Replayed the previously misrouted authenticated owner wording, “When did we
last check the backups?”, against a fresh synthetic Alpha account and canonical
healthy/stale repository records. The answer returned both repositories,
kept the infrastructure last-good time distinct from its latest stale check,
and did not offer or create a run action. It persisted in authenticated chat,
made zero model calls, and left the lifecycle database SHA-256 unchanged.
Report `/tmp/hades-backup-freshness-ui-3806769.json` (0600). This verifies the
source fix on disposable authenticated UI; production acceptance remains
pending and production was not contacted.

The failure/recovery acceptance was repeated after changing the runner to select
unused ephemeral loopback ports by default. The second run passed with the same
visible failure followed by a successful new-chat response; it again removed
all test containers/volumes/responder state. Report
`/tmp/hades-dependency-failure-ui-3809043.json` (0600). This repeat confirms
the default runner path works without relying on a manually selected port.

### Grocy concurrency and attribution status reconciliation (2026-09-26)

The capability ledger's older “Gamma active” wording said shared-resource
attribution and concurrent duplicate handling were still pending. The current
contracts establish more: `scripts/test-grocy-household-attribution.sh` passes
actor/scope audit, invalid-subject rejection, and concurrent folding of a
shared-list add; `scripts/test-grocy-spaghetti-concurrency.sh` passes two
concurrent Hermes processes with one canonical recipe, five positions, and one
shopping row per missing product. The authenticated Beta household UI has
separate evidence for canonical shared pantry/list behavior. Both concurrency
contracts passed against current source in this review. This remains synthetic;
full Alpha/Beta/Gamma Grocy UI coverage and production acceptance are not
claimed, and the production overlay still lacks the repository lock fix.

### Authenticated Grocy UI across Alpha, Beta, and Gamma (2026-09-26)

Extended the disposable authenticated Grocy acceptance to exercise all three
synthetic roles. Beta performed the established household flow (shared pantry,
recipe feasibility and explicit list updates, safe unit conversion, idempotent
retry, outage honesty, and actor audit). Separate Alpha and Gamma sessions read
the shared canonical pantry and shopping list after Beta's writes; Gamma was
denied access to Beta's private chat (HTTP 401/403). The UI acceptance also
asserted the exact canonical Grocy request counts and household actor/scope
audit. The local model responder handled only Open WebUI title/suggestion/tag
metadata; no user inference was delegated to it.

The first full run exposed a real current-turn routing defect: a fresh shopping
list question was sent to the read handler with the whole conversation, so an
older pantry question won. The handler now receives only the current user turn;
a strict Hermes runtime regression verifies the exact input after historical
"Add milk" / "Added milk" wording. One follow-up browser run also found that
Alpha's second chat turn could remain as an unanswered placeholder without
reaching Hermes. Isolating that independent list check in a new authenticated
chat made the acceptance deterministic.

Final synthetic triad report: `/tmp/hades-grocy-household-ui-3935027.json`
(mode 0600). `scripts/test-grocy-household-attribution.sh`,
`scripts/test-grocy-read-routing-hermes-runtime.sh`, and the full
`scripts/test-grocy-authenticated-household-ui.sh` passed. Disposable
containers, volume, responder, and fixture state were removed. Production was
not contacted or changed; production concurrency acceptance remains gated.

### Agent Zero Operator evidence reconciliation (2026-09-26)

The latest synthetic live Operator acceptance supersedes the earlier ledger
wording that left all browser/runtime acceptance open. On disposable Fedora 44
discovery Guest A, synthetic Alpha/Beta/Gamma LLDAP sign-in produced stable
WebUI subjects; only mapped Alpha with current `hades-owner` membership was
allowed through the loopback gateway. Household, missing/invalid sessions, and
Alpha after membership revocation failed closed; restoring membership allowed
the next request. Native Agent Zero login/logout and WebUI identity isolation,
enabled/disabled doctor, installer rerun, and disable recovery all passed.
Recovery removed the auth service, proxy and gateway listener, restored direct
WebUI access/config ACL, and preserved volumes and identities. The pinned
Nginx HTTP/WebSocket, cookie isolation, revocation and loopback fixture also
passes on SELinux-enforcing Fedora.

This is synthetic live acceptance on a discovery guest, not pristine Guest B
or owner acceptance. The gateway is disabled after recovery and remains
optional/disabled by default. Supported launcher/direct-URL acceptance and
owner dogfood remain open. Production was not changed.

### Agent Zero Operator access path documentation (2026-09-26)

`docs/agent-zero.md` now explains the optional gateway's host-local URL,
private SSH local-forward command, dual HADES/Agent Zero authentication,
revocation timing, and safe disable procedure. It explicitly says that the
external-workstation tunnel has not been live-tested. The Fedora discovery
guest used for prior acceptance is no longer present (`virsh list --all` is
empty), so this run did not claim external tunnel acceptance or recreate a
guest. Existing renderer, pinned Nginx proxy, verified-session, and policy
contracts all pass. No production access or mutation occurred.

### Health Watch cross-worker preview precedence through Hermes runtime (2026-09-26)

The existing Health Watch route test already models stale process-local state
against a newer persisted preview, but it did not pass through the normal
Hermes turn wrapper. Added `scripts/test-health-watch-hermes-runtime.sh` to
exercise both race directions on the pinned Hermes runtime with a temporary
private SQLite store: stale worker-local create versus current persisted share,
and stale worker-local unshare versus current persisted create. Both turns
complete with zero model calls. The first applies only the persisted share,
creates no duplicate automation, and clears its preview; the second leaves the
current create preview intact and performs no unshare while the runner is
unavailable. `scripts/test-health-watch-contract.sh` and the Hermes runtime
contract pass. This is synthetic repository evidence, not browser or production
acceptance. Production was not contacted or changed.

### Health Watch cross-worker authenticated browser acceptance (2026-09-26)

The pinned Hermes runtime wrapper regression is now exercised through a real
authenticated Open WebUI chat using synthetic Alpha and Beta identities and
two isolated Hermes gateway processes sharing a temporary Health Watch
SQLite store. A local test router presented one model and routed the same
conversation's create preview to worker A, share preview to worker B, and
bare `Yes` confirmation back to worker A. The share preview persisted across
workers; worker A applied the persisted share rather than its stale local
create cache. All three user turns persisted in one Alpha chat, and canonical
state contained exactly one original watch shared to Beta. The browser report
is `/tmp/hades-health-watch-cross-worker-ui-<run>.json` (mode 0600). This is
synthetic acceptance, not owner acceptance. Production was not contacted or
changed; the production overlay update remains separately authorized.

### Authenticated synthetic owner month-to-date finance comparison (2026-09-26)

The disposable Alpha/Beta Open WebUI + Hermes harness now exercises the current
month-over-month route through authenticated chat. Synthetic Alpha received a
same-calendar-day comparison ($300 across three current expense rows versus
$200 in the prior month), identified restaurant and grocery increases, excluded
income, disclosed the pending-row treatment, and stated that the result is
historical rather than a live balance or forecast. Beta received the owner-only
denial before inference. The model endpoint was deliberately unavailable, chat
history persisted, and both the TaskStore and synthetic CSV hashes were
unchanged. Report: `/tmp/hades-finance-month-over-month-ui-final.json` (0600).
The finance source, statement-window, and household-denial contracts plus this
authenticated UI acceptance pass. No real finance file, Actual service, or
production state was accessed.

### Owner recipe serving resize acceptance rerun (2026-09-26)

The disposable authenticated owner-only flow passed against synthetic Grocy
and Open WebUI. The owner previewed a change to six servings, confirmed in the
same chat, and canonical Grocy read-back showed exactly one write with
`base_servings=6`. A fresh preview followed by cancellation produced no second
write. Report `/tmp/hades-grocy-owner-serving-ui-retry.json` (mode 0600).
The harness dismissed the overlapping first-run update notice and used normal
send clicks. Containers and volumes were absent after completion; production
was not contacted or changed. This closes the previously parked browser
acceptance gap for this owner-only workflow on the disposable target.

### Cross-chat owner recipe-serving confirmation boundary (2026-09-26)

Extended the disposable authenticated owner-serving journey to use an
independent browser context with the same synthetic Alpha identity. A serving
preview was created in chat A; a bare confirmation in chat B was rejected
with a clear no-change response. A canonical Grocy read verified the serving
count remained at four, then chat A confirmed its own preview and Grocy
confirmed the single update to six. A second preview was canceled without a
write. `scripts/test-grocy-owner-serving-authenticated-ui.sh` passed and its
request audit asserts exactly one serving PUT. This is synthetic authority
boundary acceptance; production was not contacted or changed.

### Household cannot apply owner recipe-serving preview (2026-09-26)

Extended the same synthetic serving journey with authenticated Beta while
Alpha's preview remained pending. Beta's explicit request to resize the recipe
received the owner-only explanation. The complete Grocy request audit remained
limited to Alpha's preview reads, the independent same-owner cross-chat no-op,
Alpha's one confirmed PUT/read-back, and cancellation preview; no household
Grocy request or mutation occurred. Alpha's original chat still applied the
preview. `scripts/test-grocy-owner-serving-authenticated-ui.sh` passed, and
cleanup left no test containers or volumes. Production was not contacted.

### Completed-action correction and recipe inventory regression (2026-09-26)

The authenticated disposable Alpha/Beta/Gamma household rehearsal now includes
Beta adding milk to the shared list and then correcting the request to put milk
in a recipe. The rendered response says the list add already happened and was
verified, says no recipe was changed, preserves the owner-only recipe boundary,
and offers list removal without performing it. Tool-catalog inspection showed
no recipe creation/update/ingredient tools on the household correction path;
the synthetic Grocy audit retained the single intended shopping-list POST and
no recipe write. The flow also verified a fresh canonical read, chat persistence,
Gamma's shared-state read, and Gamma's inability to read Beta's private chat.
Report `/tmp/hades-grocy-household-ui-1459958.json` (mode 0600).

That run first exposed a parser regression: “Which recipes can we make right
now?” matched `can we make` as a specific recipe request and looked for a recipe
named “right now.” Inventory intent now suppresses the specific-name matcher.
`scripts/test-grocy-read-routing-hermes-runtime.sh` passes with a synthetic
canonical Grocy response, and `scripts/test-grocy-authenticated-household-ui.sh`
passes end-to-end. Disposable containers and volumes were removed. No
production endpoint was contacted or changed.

### Server-status wording safety regression (2026-09-26)

The production incident prompt, “Is everything okay with the servers?”, already
has a deterministic pinned-Hermes runtime regression: its configured model
endpoint is unavailable, yet the current homelab fixture returns canonical
read-only status with zero model calls and leaves the synthetic Task approval
unchanged. Extended that same route contract with ordinary equivalents,
“How are the servers doing?” and “Are all the computers okay?” Both resolve to
the bounded read-only homelab composition, make zero model calls, do not claim a
personal-memory update, and preserve the pending approval. The automatic
Hindsight retain gate separately classifies these live-status turns as
nonpersonal. `scripts/test-task-chat-hermes-runtime.sh`,
`scripts/test-hades-memory-intent.sh`, and
`scripts/test-homelab-service-health-contract.py` pass.

This strengthens source/runtime containment evidence only. The historical
production response claimed a personal-memory update without a recorded tool
call; whether any backend effect occurred remains unknown. No production prompt
was replayed, no memory rows were inspected, and no production state changed.

### Same-chat acceptance of an optional recipe shortage offer (2026-09-26)

The synthetic household browser flow now accepts “Yes, please” immediately
after HADES offers to add a known recipe shortage. The action is bound to the
authenticated subject and server chat, expires after ten minutes, and is
consumed only after a fresh canonical recipe/stock check matches the offer.
The existing cross-process lock, mutation audit, and canonical list read-back
remain in use. The run verified one missing-eggs write; a subsequent explicit
recipe add saw the existing row and did not duplicate it. Decline and
cross-chat confirmations remained no-write; compound confirmation is rejected
for a clear standalone response, and changed stock is rejected in the runtime
contract. Known expired stock no longer suppresses a necessary list addition.
The full authenticated Alpha/Beta/Gamma household acceptance passed; report
`/tmp/hades-grocy-household-ui-1811246.json` (0600). Runtime and UI tests passed,
and disposable resources were cleaned. No production endpoint, real household
data, or production state was contacted or changed.


### Weekly partial-result sharing — current evidence reconciliation (2026-09-26)

Historical entries above that say the full weekly partial-failure composition is unverified predate the authenticated Alpha/Beta/Gamma run and are superseded for synthetic acceptance. `HADES_TASK_ATTENTION_WEEKLY_PARTIAL=1 bash scripts/test-task-attention-authenticated-ui.sh` passed against the disposable pinned Open WebUI image and actual Hermes gateway. The synthetic Grocy source failed while Server and Backup remained healthy: Alpha and explicitly shared Beta received the full disclosure, while unshared Gamma received no summary content. Responses persisted in each authenticated chat. The harness used a deliberately unavailable model endpoint, did not disable a production dependency, and cleaned its container and volume. Mode-0600 report: `/tmp/hades-task-attention-1877292.json`. A live n8n/source outage remains untested.

### Weekly n8n source-failure runtime — synthetic only (2026-09-27)

The pinned n8n 2.40.5 image imported and executed the actual
`weekly-household-summary-n8n.json` graph with only its trigger and URLs
rewritten in a temporary fixture. Synthetic Grocy returned HTTP 503 while
Backup and server health returned healthy results. `onError: continueRegularOutput`
allowed the workflow to finish; the merged result retained the HTTP 503/error,
synthetic healthy Backup body, and normalized `hades_state=UP`. All three source
branches were called exactly once. `python3 scripts/test-weekly-n8n-source-outage.py`
passes and uses no production endpoint, credential, workflow, or data. This
closes the disposable live-n8n source-outage gap only; scheduled activation and
end-to-end delivery from n8n into authenticated Open WebUI remain unconfigured
and unaccepted. The test used the already-cached pinned image and a temporary
private n8n data directory, both cleaned after exit.
