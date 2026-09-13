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
