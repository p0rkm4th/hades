# HADES

HADES is a composition of mature upstream systems for owner-facing local
intelligence. It is intentionally not a new agent runtime, memory database,
workflow engine, or chat frontend.

Hermes owns intelligence and execution, Open WebUI owns the interface,
Hindsight owns durable semantic memory, and authoritative domain systems own
live domain state. HADES uses configuration and small adapters only where a
supported integration is unavailable.

## Getting started

HADES is intended for a private, single-household deployment managed by a
technical operator. Supported reconstruction targets are systemd hosts running
Fedora Server 44 or Rocky Linux 9/10, with at least 2 CPU cores, 8 GiB RAM
available to HADES after OS overhead (allocate 10 GiB to Fedora Cloud guests),
and 40 GiB free storage when pinned images need to be downloaded (8 GiB when the
complete image set is already cached). The current Open WebUI image requires
x86-64-v2 on x86-64 systems; ARM64 is supported by the installer contract. The
default WebUI listener is loopback-only. For remote access, use a separately
managed private proxy or SSH tunnel; do not expose service ports directly to
the public internet.

Installation requires explicit operator configuration for the model endpoint,
identity, secrets, and private runtime records. The example at
[`config/operator-inputs.env.example`](config/operator-inputs.env.example) is
a v1 legacy-compatible template. For new production installations, start from
the [v2 operator-input template](config/operator-inputs-v2.env.example); it
contains placeholders and still needs operator configuration. Fill in only
private copies and keep them out of Git. Scripts named
`create-synthetic-*` and `create-generated-private-inputs.sh` make disposable
test fixtures and must not be used as real household or production
credentials; the latter marks its output so production install, doctor, and
validation reject it.

Follow the [clean reconstruction procedure](docs/reconstruction.md) for the
canonical sequence. Minimal Fedora Cloud images may not include Git; install
that one bootstrap package with the operating system package manager before
cloning. Then clone this repository onto the intended guest, review the host
preparation plan, apply the supported prerequisites, prepare
the protected operator inputs and deployment records, run installer preflight,
install, then run the doctor and functional validator. The installer preserves
identity and application state on reruns. Consult the linked procedure for the
required private inputs and exact commands; production installation is not a
single-command setup until those operator-owned values and records exist.
Fresh installations also bootstrap pinned Grocy first so the operator can
change Grocy's default password and issue the API key required by HADES. The
Grocy key must be issued by Grocy; random key material will not work.

After installation:

- **Verify:** run `scripts/hades-doctor.sh` and
  `scripts/validate-install.sh` with the same protected operator-input file.
- **Sign in:** use the private WebUI address selected by the operator. Accounts
  are managed through the configured identity directory; there is no shared
  default password or public login endpoint. With the default LDAP mapping,
  enter the LLDAP user ID (`uid`), not necessarily the email address. On a
  fresh WebUI database, the first successful account becomes administrator;
  later LDAP accounts receive Open WebUI's `pending` role and need approval by
  that administrator before they can use the interface. Keep this activation
  step explicit: LLDAP membership and HADES tool capabilities remain separate
  authorization checks.
- **Find state:** standard roots are `/var/lib/hades` for persistent application
  state, `/etc/hades` for private configuration, and `/var/backups/hades` for
  local backup artifacts. Confirm the actual paths in the operator input file
  before maintenance.
- **Back up and restore:** follow the component-specific procedures in
  [`docs/backup-restore.md`](docs/backup-restore.md). A repository checkout or
  local backup alone is not an off-host disaster-recovery plan; choose and
  protect an encrypted destination separately.
- **Upgrade:** use the one-component-at-a-time, backup-first process in
  [`docs/upgrade-decommission.md`](docs/upgrade-decommission.md). Automatic
  upgrades are not part of this contract.
- **Stop or remove:** use the preservation-first decommission guidance in the
  same document. The default procedure preserves application data and backups;
  permanent state deletion is a separate operator decision.

The [private-input contract](docs/private-input-contract.md) explains each
secret and endpoint, who consumes it, and how it is backed up. Optional and
owner-gated integrations should remain unset unless their separate policy and
credentials are ready.

## Repository contents

- `webui/`: Open WebUI extension assets with Odysseus-inspired themes,
  animated effects, and model capability messaging.
- `searxng/`: public-safe SearXNG seed configuration for the local web-search
  provider.
- `hermes/`: non-secret configuration examples for a Hermes gateway.
- `docs/`: integration, security, and source-of-truth decisions.
- `acceptance/`: workflow evidence requirements and status conventions.
- `config/versions.env`: authoritative pinned version contract.
- `scripts/install-hades.sh`, `scripts/hades-doctor.sh`, and
  `scripts/validate-install.sh`: bounded reconstruction tooling.

Runtime secrets, accounts, host addresses, persistent volumes, chat history,
and deployment-specific state must remain outside Git.

## Public-release boundary

This repository is source and configuration documentation only. It does not
contain a production deployment, credentials, owner data, machine-specific
paths, private network addresses, or legacy application state. Copy the
examples into a private deployment configuration and substitute local values.

Physical homelab inventories, node addresses, access procedures, deployment
provenance, and operator-only acceptance records are maintained separately in
the private `hades-infra` repository. This public repository describes the
reusable HADES application and its sanitized reconstruction contract; it is
not the operational record for a particular household or machine.

Upstream Open WebUI branding and license requirements remain in force.

Clean reconstruction is documented in [`docs/reconstruction.md`](docs/reconstruction.md).
The private value lifecycle is documented in [`docs/private-input-contract.md`](docs/private-input-contract.md).
The bounded upgrade and preservation-first decommission contract is documented
in [`docs/upgrade-decommission.md`](docs/upgrade-decommission.md).
Use `--test-mode --root DIR` for a credential-free, disposable contract
rehearsal; production installs require the explicit private operator-input file
and never create synthetic users or fixture data by default.

Before publishing a change, run
`scripts/public-history-audit.sh <base>..<head>` to scan every newly introduced
commit for local paths, private-network addresses, tailnet hostnames, and
credential-like artifacts. The no-argument `scripts/public-history-audit.sh`
mode scans all history reachable from `HEAD`, including legacy findings that
may already exist on the selected public base. Public CI fetches full history
and audits only commits added by the current push or pull request; the separate
current-tree guard checks the final snapshot.
