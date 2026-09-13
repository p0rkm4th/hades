# Owner Workflow Scoreboard

This public-safe file defines acceptance evidence requirements. Private
deployment results, accounts, prompts, URLs, and runtime data belong in local
operations records and must not be committed here.

Statuses describe integrated owner workflows, not unit-test confidence.

## Conversation

- **Current status:** PASS + PERSISTENCE
- **Authoritative system:** Hermes plus the selected local model through Open WebUI
- **Verified slice:** authenticated owner conversation, follow-up, reload, and
  continuation were verified in the deployed owner path.
- **Evidence required:** authenticated owner UI response, follow-up context,
  reload persistence, and clean tool-capability handling
- **Known limitations:** model availability, context size, and tool support are
  deployment-specific

## Memory

- **Current status:** PASS + PERSISTENCE
- **Authoritative system:** Hindsight for durable context; domain systems for
  current truth
- **Verified slice:** durable memory retain/recall and correction were verified
  through HADES. A fresh mobile owner conversation now returns the corrected
  label rather than the stale paraphrase; live domain state remains
  authoritative and persistence was checked after reload/restart.
- **Evidence:** retain through the owner UI, recall in a new session,
  correction, canonical backend verification, and reload persistence.

## Operator

- **Current status:** PASS + PERSISTENCE
- **Authoritative system:** Agent Zero for one bounded delegated task
- **Verified slice:** HADES owner API delegated a no-tool readiness task through
  the private MCP adapter and received the exact upstream response; a busy
  Agent Zero state was surfaced as an error and did not become a false success.
  A fresh authenticated delegation after the container recovered narrowed the
  API turn to the Agent Zero toolset, completed successfully, and returned the
  expected bounded response; the earlier 404 was isolated to the in-progress
  Agent Zero restart rather than accepted as success. A fresh authenticated
  mobile HADES chat also rendered the bounded `A0-DOM-READY` result after the
  Agent Zero tool completed; the DOM contained the assistant result separately
  from the submitted prompt, and the Agent Zero container remained healthy.
- **Evidence required:** bounded delegation, returned evidence, safe failure
  handling, and no unnecessary host access
- **Founding milestone:** closed. Persistent delegated context, native A2A
  interoperability, and wider operator tasks remain future hardening, not
  prerequisites for the bounded delegation contract.

## Household

- **Current status:** PASS + PERSISTENCE
- **Authoritative system:** Grocy
- **Verified slice:** HADES API owner path narrowed a grocery/stock turn to
  the canonical Grocy MCP tools and returned the live empty-stock result;
  Fresh natural-language API turns (“what food do i have?” and “do we have
  milk?”) now routed through the adaptive Qwen path, invoked
  `mcp_grocy_stock_overview_tool`, and returned two synthetic milk units;
  Grocy’s canonical stock endpoint independently matched that quantity.
  Browser automation now reaches the authenticated shell on localhost and
  Tailscale. A fresh synthetic mobile session also rendered the live Grocy
  stock answer (“HADES Synthetic Milk — 2 units”) through the normal chat
  surface; the corresponding canonical stock check matched. Mutation, reload,
  and broader household browser evidence remain open.
  The earlier empty-state turn had Grocy `/api/stock` independently confirm
  zero rows. A synthetic product
  was added through HADES, removed through a follow-up, and re-added through a
  correction turn; Grocy's shopping-list API verified the empty state and then
  exactly one canonical row. The earlier add survived a Grocy restart and a
  fresh HADES query recovered the item. A repeated add was regression-tested
  after the deployment fix: it increased the existing row's quantity instead
  of creating a duplicate. A synthetic purchase also passed the bounded
  preview → explicitly confirmed apply path; Grocy's stock API verified
  quantity 3. A follow-up consumption turn then reduced canonical stock from
  3 to 2. Natural-language apply still benefits from naming the confirmed
  workflow explicitly for the local model. A synthetic two-unit recipe passed
  both fulfillment branches: available stock reported ready, and after one
  consumption the same recipe reported one missing ingredient; stock was then
  restored to the two-unit fixture. With a one-unit shortage, recipe
  add-missing merged the required quantity into the existing shopping row
  without duplication; the fixture was restored to two stock units and one
  shopping-list unit. A controlled Grocy and Hermes restart preserved the
  recipe, stock, and shopping row; a fresh HADES query recovered the item and
  quantity. Additional read-only variations passed through the same narrowed
  route: shorthand “whats on my shopping list?” returned the canonical row,
  the informal/profane “shit do we have eggs” correctly reported no eggs from
  live stock, and a stale remembered recipe label produced an MCP error that
  the model recovered from by using Grocy’s canonical recipe name. No false
  success was emitted. A fresh synthetic mobile browser session then added
  the synthetic milk item through normal HADES chat; Grocy’s canonical
  shopping-list endpoint showed exactly one unfinished row with quantity 2,
  and reopening the chat after reload preserved the assistant result.
  The follow-up “Actually remove it from the list.” initially exposed lost
  domain context and was incorrectly treated as a generic task-list request;
  after the overlay fix, the same follow-up invoked Grocy, removed the item,
  returned a visible assistant acknowledgement, and Grocy’s canonical list
  was empty after reload.
  The same mobile session then asked whether the synthetic two-unit recipe was
  makeable; HADES rendered the available result, and Grocy’s canonical recipe
  and ingredient records independently showed a two-unit requirement against
  two units in stock. Reload preserved the recipe result. A read-only
  shorthand follow-up, “whats on my shopping list?”, rendered an empty-list
  answer, and Grocy’s canonical shopping-list endpoint independently returned
  an empty collection.
  An adversarial shorthand/profane read-only prompt, “shit do we have eggs”,
  rendered a clear no-eggs answer; canonical Grocy showed only the two
  synthetic milk units, and the response remained visible after reload.
- **Evidence required:** pantry, grocery, purchase, consumption, duplicate,
  correction, recipe-shortage, and reload-persistence workflows verified in
  Grocy through the owner UI
- **Founding milestone:** closed. Remaining wording sensitivity and additional
  pantry edge cases are future hardening.

## Homelab

- **Current status:** PREPARATION COMPLETE
- **Authoritative systems:** Proxmox VE, NetBox, and Uptime Kuma, each for its
  own domain
- **Preparation:** read-only credential templates, minimum permission scope,
  source/freshness requirements, failure behavior, and owner acceptance
  prompts are documented in `docs/homelab-readonly.md`.
- **Remaining gate:** exact endpoints and owner-approved credentials are not
  present; no real homelab service has been contacted.

## Finance

- **Current status:** SELECTED (synthetic integration); real finance
  remains BLOCKED BY OWNER AUTHORIZATION
- **Authoritative system:** Actual Budget; Firefly III is the
  fallback. Finlynq and Ledgr remain watchlisted.
- **Synthetic evidence:** four disposable candidates started; Finlynq owner UI
  accepted Batch A, reported nine duplicate Checking rows skipped on identical
  re-import while routing three other-account rows, and exposed a likely
  false-positive on the nearby same-merchant Batch B row. Actual native archive
  and Finlynq PostgreSQL restore probes passed. The published Actual 26.9.0
  client initially hit an out-of-sync migration error against the mismatched
  image; the matched stable 26.9.0 pair then loaded, imported, synced, and
  reloaded synthetic state successfully. Production still requires that pair
  to remain pinned.
- **Evidence:** `docs/adr/finance-platform.md` and
  `test-data/finance-bakeoff/`.
- **Owner UI evidence:** A designated test administrator authenticated through the real Open WebUI DOM,
  selected the staged `hermes-finance-staging` model, and submitted
  “What is my checking account balance?”. Open WebUI rendered the chat and
  rendered the canonical synthetic balance `$3,395.36`; the staged Hermes log
  records the narrowed Actual read tool completing. A separate restart/reload
  DOM probe reopened the conversation and found both the prompt and balance.
  A prior staged run correctly surfaced an Actual adapter failure when its
  disposable gateway lacked the synthetic password environment; it did not
  fabricate a balance. The canonical read-only helper independently returned
  the same Checking balance from the Actual budget.
- **Status:** PASS + PERSISTENCE for the synthetic owner read path. The stable
  matched pair, read-only MCP boundary, synthetic canonical reads/failure
  response, selected-state archive restore, owner-facing failure behavior, and
  successful owner-path canonical read are proven. Production authorization
  remains open; no real finance data, provider, or write path is present.

## Memory + household composition

- **Current status:** PASS
- **Authoritative systems:** Hindsight for the remembered label; Grocy for live
  recipe and stock state
- **Verified slice:** a synthetic recipe-fixture fact was retained through
  HADES, recalled in a later turn, and combined with live Grocy fulfillment;
  HADES reported the recipe as makeable with no missing products.
- **Evidence:** a fresh mobile chat verifies the single-turn composition path:
  Hindsight recalled the synthetic recipe label, Grocy checked live stock and
  recipe fulfillment in the same turn, and HADES rendered the recipe as
  makeable. A separate fresh mobile correction query returned the corrected
  label rather than the stale paraphrase, without changing live Grocy state;
  the result survived reload after the canonical checks.

## Multi-user identity foundation and conversation isolation

- **Current status:** PASS + PERSISTENCE (isolated staging scope)
- **Owner input:** synthetic staging authentication only; production owner
  login was not changed
- **DOM result:** not yet exercised in this checkpoint; the disposable
  Open WebUI login API returned successful authenticated sessions for
  synthetic Alpha and Beta users
- **Authoritative system:** LLDAP for directory authentication; Open WebUI
  for application subject provisioning
- **Backend verification:** LLDAP is healthy, both synthetic users bind
  successfully, and Open WebUI created two distinct subject IDs. Repeated
  LDAP login returned the same subject ID for Alpha and for Beta.
- **Conversation verification:** each synthetic user created a private chat;
  each user's list contained its own chat and not the other's, and guessed
  direct access to the other chat returned HTTP 401.
- **Reload/persistence result:** repeated logins preserved both subjects and
  chats. LLDAP and disposable Open WebUI restarts completed; both users then
  authenticated again and retained one private chat each.
- **Last verified SHA:** `78d99d3`
- **Limitations:** production remains local-authenticated. Hindsight
  per-subject namespaces, shared Grocy authorization, finance exclusion,
  Agent Zero policy, per-user settings, revocation, and real owner-UI DOM
  acceptance remain unfinished.

The clean staging fixture was rebuilt with a synthetic owner provisioned first;
the owner retained admin role while Alpha and Beta were promoted to ordinary
users. Each created a private marker chat. Each user's list contained only its
own chat, and direct requests for the other user's chat returned HTTP 401.
After an Open WebUI restart and fresh LDAP login, all three roles and stable
application subjects remained unchanged and each household user still saw only
its own chat.

## Hindsight subject namespace boundary

- **Current status:** PASS + PERSISTENCE (isolated backend staging scope)
- **Owner input:** synthetic Alpha/Beta memory fixtures only; no production
  Hindsight bank was written
- **DOM result:** not applicable to this backend contract probe; the
  owner-facing WebUI integration remains pending
- **Authoritative system:** Hindsight banks selected by the authenticated
  server-side subject
- **Backend verification:** synthetic Alpha and Beta facts were retained into
  separate `hades-user-*` banks. Each bank recalled its own restaurant fact
  and not the other bank's fact. The same result held after restarting the
  disposable Hindsight service.
- **Reload/persistence result:** PASS; both isolated banks and their facts
  survived service restart
- **Last verified SHA:** `e3053a3`
- **Limitations:** production still uses the existing `hades-owner` bank and
  static Hermes memory configuration. Owner-bank migration/mapping must be
  explicitly designed before enabling a per-user template; no production
  memory configuration was changed.

## Hermes subject-aware memory path

- **Current status:** PASS + PERSISTENCE (disposable end-to-end staging)
- **Owner input:** authenticated synthetic Alpha and Beta API sessions
- **DOM result:** not exercised in this checkpoint; the requests used the
  authenticated OpenAI-compatible path that Open WebUI calls
- **Authoritative system:** Hindsight per-subject banks selected by Hermes
  from the server-propagated session key
- **Backend verification:** Alpha retained and recalled only synthetic
  `Test Restaurant Alpha2`; Beta retained and recalled only synthetic
  `Test Restaurant Beta2`. An Alpha adversarial request for Beta's private
  preference returned Alpha's own context and no Beta fact.
- **Reload/persistence result:** Hermes and the disposable Hindsight service
  were both restarted; fresh Alpha/Beta sessions recalled their original
  private facts. Direct canonical recalls matched the same separation.
- **Last verified SHA:** `1f95b02`
- **Limitations:** this is a disposable Hermes/Hindsight path. Production
  still uses the static owner bank until migration, header configuration, and
  owner-data preservation are separately approved and verified.

## Shared Grocy through subject-aware Hermes

- **Current status:** PASS + PERSISTENCE (disposable end-to-end staging)
- **Owner input:** Alpha asked to add Milk; Beta asked for the shared grocery
  list; Alpha asked again after restart
- **DOM result:** not exercised in this checkpoint; the authenticated API
  path was used while the browser harness is unavailable
- **Authoritative system:** disposable Grocy `shopping_list` state
- **Backend verification:** Alpha's Hermes/MCP turn added Milk. Grocy's
  canonical API contained exactly one Milk row. Beta's independent subject
  read saw the same shared list and Milk entry.
- **Reload/persistence result:** Grocy and Hermes were restarted; Alpha's
  fresh subject-keyed read still saw Milk, and the canonical API still showed
  one Milk row.
- **Last verified SHA:** `e90649e`
- **Limitations:** this uses a disposable demo-mode Grocy backend and a
  synthetic adapter key. Production Grocy was not mutated; full household
  authorization and Open WebUI DOM acceptance remain pending.

## Privileged capability boundary

- **Current status:** PARTIAL (production finance exclusion; household scope
  guard staged)
- **Owner input:** none; this was a safety regression check
- **DOM result:** not exercised in this checkpoint
- **Authoritative system:** Hermes server-side tool catalog and capability
  configuration
- **Backend verification:** the API overlay no longer reconciles or narrows
  into `mcp-actual-finance-readonly`; finance cannot be enabled by a
  natural-language prompt. The production profile contains no finance toolset.
  A server-selected `hades-user-*` session scope also blocks prompt-based
  Agent Zero acquisition.
- **Reload/persistence result:** Hermes was restarted through its managed
  service after commit `78d99d3`; health recovered and the full smoke suite
  passed 9/9.
- **Limitations:** Open WebUI has not yet been configured to send the
  server-selected subject/scope header in production, so multi-user
  authorization is not enabled. A per-user capability source is still
  required before enabling finance for the owner or any future household
  policy.

## Household privileged-capability exclusion

- **Current status:** PASS (disposable Hermes capability scope)
- **Owner input:** synthetic Alpha and Beta sessions requested Agent Zero
  readiness work and private financial data
- **DOM result:** not exercised in this checkpoint; the authenticated staged
  Hermes path was used while the browser harness was unavailable
- **Authoritative system:** Hermes server-side tool catalog and subject scope
- **Backend verification:** both `hades-user-*` sessions received neither the
  Agent Zero nor finance tool. Hermes reported both capabilities unavailable,
  returned no financial value, and made no delegated call. This remained true
  when the requests used adversarial owner-like wording.
- **Reload/persistence result:** the disposable gateway remained healthy after
  the requests; production tool exposure was unchanged
- **Last verified SHA:** `6f79427`
- **Limitations:** production has not enabled subject/scope propagation. The
  production owner path retains its accepted owner-only behavior; Household
  Alpha authorization is not yet enabled.

## Directory group propagation

- **Current status:** PASS (disposable staging transport and provisioning)
- **Authoritative system:** LLDAP group membership, synchronized into
  Open WebUI's local group records
- **Backend verification:** with supported LDAP group management enabled,
  synthetic Alpha and Beta synchronized into Open WebUI's `hades-household`
  and `hades-users` groups. A harmless downstream echo request received the
  stable subject header plus `X-Hades-Groups: hades-household,hades-users`.
- **Cleanup:** a temporary header-probe provider was removed and staging was
  restarted; the staged OpenAI provider configuration is empty again.
- **Limitations:** production group propagation and capability selection remain
  unenabled; the echo provider was disposable and was removed after the test.

## Open WebUI subject-header propagation

- **Current status:** PASS (disposable staging transport)
- **Owner input:** synthetic Alpha login and a harmless header-probe prompt
- **DOM result:** not exercised in this checkpoint; the request used the same
  authenticated WebUI chat API that the frontend calls
- **Authoritative system:** Open WebUI connection-header expansion and the
  downstream Hermes gateway contract
- **Backend verification:** a disposable OpenAI-compatible echo service
  received `X-Hermes-Session-Key` containing the stable Alpha application
  subject after Open WebUI expanded `{{USER_ID}}`. The companion group header
  was present but empty, establishing that group propagation must be staged
  separately rather than inferred.
- **Reload/persistence result:** the disposable connection was removed and
  staging was restarted; its OpenAI configuration returned to empty and the
  echo listener was gone.
- **Last verified SHA:** `104bac6`
- **Limitations:** this proves transport/header expansion, not production
  identity cutover or a full Hermes model turn. Production remains unchanged.

## Synthetic account revocation

- **Current status:** PARTIAL
- **Owner input:** synthetic Beta account only; production identities and data
  were not changed
- **DOM result:** not exercised in this checkpoint; supported auth and admin
  APIs were used while the browser harness was unavailable
- **Authoritative systems:** LLDAP for new authentication; Open WebUI for
  application sessions and user records
- **Backend verification:** deleting Beta in LLDAP caused a new LDAP login to
  fail with HTTP 400. An already-issued Open WebUI bearer token still worked
  with HTTP 200. `scripts/revoke-directory-user.sh` now performs the ordered
  supported deletions—Open WebUI first, then LLDAP—and verifies both stores;
  the old token then failed with HTTP 401.
- **Reload/persistence result:** the boundary was verified in live disposable
  staging; no production account was touched
- **Last verified SHA:** `571a5da`
- **Limitations:** automatic directory event synchronization is not
  implemented. Household Alpha must not be declared until the operational
  boundary is documented for production and survives restart/recovery.

The ordered bridge was re-run against the clean group-enabled fixture: Beta's
pre-revocation session returned HTTP 200, the same token returned HTTP 401
afterward, and a fresh LDAP login returned HTTP 400. No production account was
involved.

## Household model visibility and WebUI-to-Hermes memory

- **Current status:** PASS + PERSISTENCE (disposable end-to-end staging)
- **Owner input:** Alpha and Beta authenticated through LDAP and used the
  normal Open WebUI chat API
- **DOM result:** not exercised in this checkpoint; the same authenticated API
  path used by the frontend was exercised
- **Authoritative systems:** Open WebUI model access records; Hermes and
  subject-scoped Hindsight banks
- **Backend verification:** the direct Hermes model catalog returned `hades`,
  while Open WebUI initially hid it from ordinary users because no local
  access record existed. The supported model-access endpoint created a
  household-group read grant; both Alpha and Beta then saw `hades`. Through
  that model, each user stored and recalled its own restaurant marker through
  WebUI → Hermes → Hindsight, with the other user's marker absent.
- **Reload/persistence result:** each user's subject remained stable after
  LDAP re-login; the provider and disposable Hermes copy were removed after
  verification, leaving staging clean.
- **Last verified SHA:** `25390e1`
- **Limitations:** production model access, subject headers, and per-user
  Hindsight mapping remain unenabled until an owner-preserving migration is
  separately approved.

## User-specific settings isolation

- **Current status:** PASS + PERSISTENCE (isolated staging scope)
- **Owner input:** synthetic Alpha and Beta accounts selected distinct
  synthetic theme values and the Rain background effect
- **DOM result:** not exercised in this checkpoint; the supported user
  settings API was used while the browser harness was unavailable
- **Authoritative system:** Open WebUI per-user settings store
- **Backend verification:** Alpha read back only its `alpha-theme` setting and
  Beta read back only its `beta-theme` setting. A newly provisioned LDAP user
  initially entered Open WebUI as `pending`; the supported admin promotion to
  `user` was required before ordinary settings access succeeded.
- **Reload/persistence result:** after restarting disposable Open WebUI and
  logging both users in again, each retained its own theme and Rain effect.
- **Last verified SHA:** `705487b`
- **Limitations:** this proves application preference isolation in staging,
  not production multi-user cutover or browser DOM rendering.

## Identity recovery rehearsal

- **Current status:** PASS (synthetic staging scope)
- **Owner input:** none; only disposable LLDAP directory data was used
- **DOM result:** not applicable to the backup contract
- **Authoritative system:** LLDAP persistent directory database
- **Backend verification:** the quiesced staging LLDAP data was copied to a
  separate restore target; SQLite `quick_check` returned `ok`, and the
  restored pinned LLDAP image reached HTTP 200 health on an isolated port.
- **Reload/persistence result:** the original staging directory remained
  running and unchanged; the restored container was stopped and auto-removed
  after verification
- **Last verified SHA:** `bf319b4`
- **Limitations:** this proves synthetic directory backup/start recovery, not
  owner-data recovery or automatic restoration of Open WebUI subject mappings.
  The production identity cutover remains gated.
