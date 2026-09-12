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

- **Current status:** PARTIAL
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

## Household

- **Current status:** PARTIAL
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

- **Current status:** SELECT WITH CONDITIONS (synthetic bakeoff); real finance
  remains BLOCKED BY OWNER AUTHORIZATION
- **Provisional authoritative system:** Actual Budget; Firefly III is the
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
- **Owner UI evidence:** test administrator authenticated through the real Open WebUI DOM,
  selected the staged `hermes-finance-staging` model, and submitted
  “What is my checking account balance?”. Open WebUI rendered the chat and
  preserved the prompt after reload. The staged run correctly surfaced an
  Actual adapter failure because the disposable gateway restart lacked its
  synthetic password environment; it did not fabricate a balance.
- **Remaining gate:** complete a successful HADES owner-path canonical run.
  The stable matched pair, read-only MCP boundary, synthetic canonical
  reads/failure response, selected-state archive restore, and owner-facing
  failure behavior are proven. Production authorization remains open; no
  real finance data, provider, or write path is present.

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
