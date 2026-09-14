# Finance read-only integration plan

This document is the production boundary. HADES has no real finance
credentials, linked provider accounts, or finance runtime integration. Actual
Budget is the selected canonical platform for synthetic HADES integration, with
the small read-only MCP adapter in `integrations/actual-finance-readonly/`
reserved for isolated staging until owner authorization is explicit.

## Boundary and authority

Actual Budget is the authority for imported account and transaction data.
Hindsight may remember preferences such as category names, but must never
supply balances, transactions, or affordability figures. Provider-linked
accounts remain an owner decision and are not connected by this campaign.

The first implementation is read-only and uses the official Actual Node client
behind the MCP boundary. It must use a matching pinned server/client revision,
cache only the selected budget locally, and expose only account, balance,
transaction, and status reads. It must never expose Actual's mutation, import,
sync, provider-link, reconciliation-write, or money-movement methods.

## Secret-safe placeholders

```dotenv
ACTUAL_SERVER_URL=<private-local-or-container-url>
ACTUAL_API_MODULE=<private-pinned-client-path>
ACTUAL_PASSWORD_FILE=<private-secret-file>
ACTUAL_BUDGET_GROUP_ID=<private-selected-budget-id>
```

No access token, account identifier, transaction, or real financial value may
be committed to this repository or used in synthetic acceptance evidence.

## Required freshness and coverage behavior

Every finance answer must identify, in owner-friendly language:

- provider and account coverage;
- last successful provider update and local sync time;
- whether pending transactions are included;
- date range and pagination completeness;
- errors, stale Items, or missing accounts.

The adapter reports the canonical source, retrieval time, server version,
Actual local sync metadata, and computed freshness on every successful read.
If the server is unavailable, the budget cannot be loaded, or freshness is
unknown, the adapter returns an explicit failure and HADES must avoid
confident affordability or “how much did I spend” claims. Local memory must
never fill a missing live finance answer.

## Owner acceptance prompts

After the owner authorizes the selected finance environment and confirms the
read-only scope:

- “How much did I spend on coffee?”
- “What subscriptions do I have?”
- “What’s coming out before payday?”
- “Why was spending higher this month?”
- “Can I afford $400 this weekend?”

Acceptance must compare the HADES response with Actual's canonical records,
verify reload/restart continuation, and test an unavailable/stale-server
response. No money movement, account changes, or financial writes are
permitted.

## Genuine owner gate

The remaining action is explicit owner authorization of the finance
environment, selected budget, accounts, retention policy, and secret storage.
Until those choices and credentials exist, finance remains blocked by an owner
gate and must not be simulated with real-looking data.

Reference: [Actual Budget API](https://actualbudget.org/docs/api/).
