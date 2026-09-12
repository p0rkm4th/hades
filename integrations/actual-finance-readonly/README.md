# Actual Budget read-only adapter

This is a deliberately small stdio MCP boundary for the selected Actual
Budget platform. It exposes only account, transaction, and status reads. It
does not expose the official client's mutation, import, sync, provider-link,
or money-movement methods.

The bridge uses the official [`@actual-app/api`](https://actualbudget.org/docs/api/)
Node client because Actual's supported programmatic interface is not a REST
API. Pin the client and server to matching supported revisions; do not use a
moving nightly channel in production.

Required private environment:

```text
ACTUAL_API_MODULE=/path/to/@actual-app/api/dist/index.js
ACTUAL_SERVER_URL=http://actual:5006
ACTUAL_DATA_DIR=/persistent/read-cache
ACTUAL_PASSWORD_FILE=/run/secrets/actual-password
ACTUAL_BUDGET_GROUP_ID=<selected-budget-group-id>
```

Example Hermes configuration:

```yaml
mcp_servers:
  actual-finance-readonly:
    command: python
    args: ["/path/to/Hades/integrations/actual-finance-readonly/server.py"]
    env:
      ACTUAL_READONLY_HELPER: /path/to/Hades/integrations/actual-finance-readonly/actual_client.js
      ACTUAL_API_MODULE: /path/to/pinned/@actual-app/api/dist/index.js
      ACTUAL_SERVER_URL: http://actual:5006
      ACTUAL_DATA_DIR: /persistent/read-cache
      ACTUAL_PASSWORD_FILE: /run/secrets/actual-password
      ACTUAL_BUDGET_GROUP_ID: <selected-budget-group-id>
```

Keep this server private to Hermes. The password is read from a secret file
and is never returned by a tool. A stale or unavailable read must be surfaced
as a failure; the adapter must not infer current financial state from memory.

For imported transfers, normalize each provider row to a distinct import
identity and use Actual's transfer-payee semantics when creating a linked
counterpart. Do not reuse one global `imported_id` for both sides of a pair;
Actual's reconciliation logic may treat the second row as the same imported
transaction.
