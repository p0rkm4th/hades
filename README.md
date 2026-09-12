# HADES

HADES is a composition of mature upstream systems for owner-facing local
intelligence. It is intentionally not a new agent runtime, memory database,
workflow engine, or chat frontend.

Hermes owns intelligence and execution, Open WebUI owns the interface,
Hindsight owns durable semantic memory, and authoritative domain systems own
live domain state. HADES uses configuration and small adapters only where a
supported integration is unavailable.

## Repository contents

- `webui/`: Open WebUI extension assets with Odysseus-inspired themes,
  animated effects, and model capability messaging.
- `searxng/`: public-safe SearXNG seed configuration for the local web-search
  provider.
- `hermes/`: non-secret configuration examples for a Hermes gateway.
- `docs/`: integration, security, and source-of-truth decisions.
- `acceptance/`: workflow evidence requirements and status conventions.

Runtime secrets, accounts, host addresses, persistent volumes, chat history,
and deployment-specific state must remain outside Git.

## Public-release boundary

This repository is source and configuration documentation only. It does not
contain a production deployment, credentials, owner data, machine-specific
paths, private network addresses, or legacy application state. Copy the
examples into a private deployment configuration and substitute local values.

Upstream Open WebUI branding and license requirements remain in force.

Before publishing changes, run `scripts/public-history-audit.sh HEAD` to check
the complete reachable history for local paths, private-network addresses,
tailnet hostnames, and credential-like artifacts.
