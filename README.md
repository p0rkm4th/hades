# HADES

HADES is a self-hosted personal and household AI: local chat, durable
context, canonical household inventory and recipes, bounded web research, and
optional typed automation. It can run on one ordinary Linux machine or use
explicit private model servers. Cloud routing is opt-in and never silently
changes authority.

## Preview install

This repository currently publishes the prerelease branch/tag
`public-release-candidate` / `v0.1.0-preview.1`:

```sh
curl -fsSL https://raw.githubusercontent.com/p0rkm4th/Hades/public-release-candidate/install.sh | \
  HADES_REPO_REF=public-release-candidate bash -s -- install \
  --inputs /etc/hades/operator-inputs.env
```

Review the script or download it first. The default supported path is one
Linux host with 2+ CPU cores, 8 GiB RAM, 40 GiB free disk, and Docker Compose.
Advanced distributed profiles are optional.

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
- `config/versions.env`: authoritative pinned version contract.
- `install.sh` and `scripts/hades`: reproducible bootstrap and lifecycle CLI.
- `scripts/install-hades.sh`, `scripts/hades-doctor.sh`, and
  `scripts/validate-install.sh`: bounded reconstruction primitives.

Runtime secrets, accounts, host addresses, persistent volumes, chat history,
and deployment-specific state must remain outside Git.

## Public-release boundary

This repository is source and configuration documentation only. It does not
contain a production deployment, credentials, owner data, machine-specific
paths, private network addresses, or legacy application state. Copy the
examples into a private deployment configuration and substitute local values.

Upstream Open WebUI branding and license requirements remain in force.

Installation and lifecycle usage is documented in [`docs/installation.md`](docs/installation.md).
Clean reconstruction is documented in [`docs/reconstruction.md`](docs/reconstruction.md).
The private value lifecycle is documented in [`docs/private-input-contract.md`](docs/private-input-contract.md).
The bounded upgrade and preservation-first decommission contract is documented
in [`docs/upgrade-decommission.md`](docs/upgrade-decommission.md).
Use `--test-mode --root DIR` for a credential-free, disposable contract
rehearsal; production installs require the explicit private operator-input file
and never create synthetic users or fixture data by default.

Before publishing changes, run `scripts/public-history-audit.sh HEAD` to check
the complete reachable history for local paths, private-network addresses,
tailnet hostnames, and credential-like artifacts.
