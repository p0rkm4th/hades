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
  through HADES, with live domain state kept authoritative and persistence
  checked after reload/restart.
- **Evidence required:** retain through the owner UI, recall in a new session,
  correction, canonical backend verification, and reload persistence

## Operator

- **Current status:** PARTIAL
- **Authoritative system:** Agent Zero for one bounded delegated task
- **Verified slice:** HADES owner API delegated a no-tool readiness task through
  the private MCP adapter and received the exact upstream response; a busy
  Agent Zero state was surfaced as an error and did not become a false success.
  A fresh authenticated delegation after the container recovered narrowed the
  API turn to the Agent Zero toolset, completed successfully, and returned the
  expected bounded response; the earlier 404 was isolated to the in-progress
  Agent Zero restart rather than accepted as success.
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
  Browser-DOM acceptance remains pending because browser automation is not
  installed on the dogfood host.
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
  success was emitted.
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

- **Current status:** PREPARATION COMPLETE / OWNER GATE
- **Authoritative system:** owner-authorized finance provider, initially via
  read-only Plaid Transactions Sync
- **Preparation:** cursor/pagination, freshness, coverage, pending-versus-
  posted, removal/reconciliation, and safe failure requirements are documented
  in `docs/finance-readonly.md`.
- **Remaining gate:** provider, accounts, environment, retention policy, and
  private webhook authorization; no real finance data is present.

## Memory + household composition

- **Current status:** PARTIAL
- **Authoritative systems:** Hindsight for the remembered label; Grocy for live
  recipe and stock state
- **Verified slice:** a synthetic recipe-fixture fact was retained through
  HADES, recalled in a later turn, and combined with live Grocy fulfillment;
  HADES reported the recipe as makeable with no missing products.
- **Remaining evidence:** browser-DOM/new-session acceptance and a correction
  turn that proves the remembered label can change without overriding live
  Grocy state. The correction branch is now API-verified; browser-DOM evidence
  remains open.
