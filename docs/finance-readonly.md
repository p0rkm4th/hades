# Finance read-only integration plan

This document is preparation only. HADES has no Plaid credentials, linked
Items, account data, or finance runtime integration.

## Boundary and authority

Plaid (or the owner-approved finance provider) is the authority for account and
transaction data. Hindsight may remember preferences such as category names,
but must never supply balances, transactions, or affordability figures.

The first implementation must be read-only and use Plaid Transactions Sync.
It should maintain the provider cursor privately, paginate until complete, and
reconcile `added`, `modified`, and `removed` transactions by provider ID.
Pending and posted transactions must remain distinguishable; a pending item
must not be counted as settled spending without saying so.

## Secret-safe placeholders

```dotenv
HADES_FINANCE_PROVIDER=plaid
HADES_PLAID_ENV=<sandbox-or-production-owner-choice>
HADES_PLAID_CLIENT_ID=<private>
HADES_PLAID_SECRET=<private>
HADES_PLAID_ACCESS_TOKEN=<private-owner-authorized-item-token>
HADES_PLAID_WEBHOOK_URL=<private-https-endpoint>
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

Use `SYNC_UPDATES_AVAILABLE` to trigger incremental sync after the initial
cursor is established. A provider refresh is not the same as a successful
transaction sync. If data is stale or incomplete, HADES must say so and avoid
confident affordability or “how much did I spend” claims.

## Owner acceptance prompts

After the owner authorizes a provider and confirms the read-only scope:

- “How much did I spend on coffee?”
- “What subscriptions do I have?”
- “What’s coming out before payday?”
- “Why was spending higher this month?”
- “Can I afford $400 this weekend?”

Acceptance must compare the HADES response with the provider’s canonical
records, exercise pending-versus-posted behavior, verify a cursor/reload
continuation, and test an unavailable/stale-provider response. No money
movement, account changes, or financial writes are permitted.

## Genuine owner gate

The remaining action is explicit owner authorization of the provider,
environment, accounts, retention policy, and a private HTTPS webhook path.
Until those choices and credentials exist, finance remains blocked by an owner
gate and must not be simulated with real-looking data.

References: [Plaid Transactions API](https://plaid.com/docs/api/products/transactions/),
[Plaid Transactions Sync guidance](https://plaid.com/docs/transactions/sync-migration/),
and [Plaid transaction states](https://plaid.com/docs/transactions/transactions-data/).
