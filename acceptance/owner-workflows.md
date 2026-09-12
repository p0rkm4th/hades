# Owner Workflow Scoreboard

This public-safe file defines acceptance evidence requirements. Private
deployment results, accounts, prompts, URLs, and runtime data belong in local
operations records and must not be committed here.

Statuses describe integrated owner workflows, not unit-test confidence.

## Conversation

- **Current status:** TEMPLATE
- **Authoritative system:** Hermes plus the selected local model through Open WebUI
- **Evidence required:** authenticated owner UI response, follow-up context,
  reload persistence, and clean tool-capability handling
- **Known limitations:** model availability, context size, and tool support are
  deployment-specific

## Memory

- **Current status:** TEMPLATE
- **Authoritative system:** Hindsight for durable context; domain systems for
  current truth
- **Evidence required:** retain through the owner UI, recall in a new session,
  correction, canonical backend verification, and reload persistence

## Operator

- **Current status:** PARTIAL
- **Authoritative system:** Agent Zero for one bounded delegated task
- **Verified slice:** HADES owner API delegated a no-tool readiness task through
  the private MCP adapter and received the exact upstream response; a busy
  Agent Zero state was surfaced as an error and did not become a false success.
- **Evidence required:** bounded delegation, returned evidence, safe failure
  handling, and no unnecessary host access

## Household

- **Current status:** PARTIAL
- **Authoritative system:** Grocy
- **Verified slice:** HADES API owner path narrowed a grocery/stock turn to
  the canonical Grocy MCP tools and returned the live empty-stock result;
  Grocy `/api/stock` independently confirmed zero rows. A synthetic product
  was added through HADES, removed through a follow-up, and re-added through a
  correction turn; Grocy's shopping-list API verified the empty state and then
  exactly one canonical row. The earlier add survived a Grocy restart and a
  fresh HADES query recovered the item. A repeated add was regression-tested
  after the deployment fix: it increased the existing row's quantity instead
  of creating a duplicate. A synthetic purchase also passed the bounded
  preview → explicitly confirmed apply path; Grocy's stock API verified
  quantity 3. A follow-up consumption turn then reduced canonical stock from
  3 to 2. Natural-language apply still benefits from naming the confirmed
  workflow explicitly for the local model.
- **Evidence required:** pantry, grocery, purchase, consumption, duplicate,
  correction, recipe-shortage, and reload-persistence workflows verified in
  Grocy through the owner UI
