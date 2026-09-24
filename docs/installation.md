# HADES installation and lifecycle guide

HADES is a source-controlled integration layer around upstream services. A
fresh install needs a supported Linux host, Docker Compose, a private operator
input file, and an explicitly reachable model endpoint. It does not create
users, import finance data, invent credentials, or silently route prompts to a
cloud provider.

## Quick start

Review a tagged or commit-pinned release first, then run the bootstrap with a
protected operator-input file:

```sh
curl -fsSL https://raw.githubusercontent.com/p0rkm4th/Hades/main/install.sh | \
  sudo HADES_REPO_REF=<reviewed-ref> bash -s -- install \
  --inputs /etc/hades/operator-inputs.env
```

For a local checkout:

```sh
sudo scripts/hades preflight --inputs /etc/hades/operator-inputs.env
sudo scripts/hades install --inputs /etc/hades/operator-inputs.env
sudo scripts/hades doctor --inputs /etc/hades/operator-inputs.env
sudo scripts/hades validate --inputs /etc/hades/operator-inputs.env
```

The supported reconstruction target is Fedora Server 44 or Rocky Linux 9/10,
x86_64 or aarch64, with systemd, at least 2 CPU cores, 8 GiB RAM, and 40 GiB
free disk. See [`host-contract.md`](host-contract.md) and
[`config/operator-inputs.env.example`](../config/operator-inputs.env.example).

## Lifecycle commands

`preflight` is non-mutating. `install` is idempotent and keeps existing state.
`doctor` and `status` are read-only. `repair` reruns the installer after an
operator fixes a failed dependency. `reconfigure` rerenders explicit private
records and reruns the installer. `backup` creates a protected SQLite
checkpoint; native Hindsight, finance, and other component exports remain
component-specific. `restore` verifies a checkpoint but deliberately stops at
the native restore boundary so a generic script cannot corrupt authoritative
state. `upgrade` handles one bounded component with a retained rollback copy.
`uninstall --confirm` stops runtime services but preserves source, state,
secrets, and backups; permanent deletion is intentionally outside this tool.

All commands fail closed on missing or unsafe inputs. Secret values belong in
mode-0600/0640 files and are never accepted as command-line arguments. The
repository manifest pins tracked dependencies; operator inputs cannot override
those pins.

After installation, `scripts/hades version` reports release/source identity and
`scripts/hades doctor --json` reports machine-readable provenance and health
metadata without secret values.

## Model paths

The model endpoint is explicit in the operator input. It may point to a local
CPU runtime, a local GPU/model server, an existing private OpenAI-compatible
server, or an owner-approved cloud/frontier endpoint. HADES does not silently
change between these paths. If a cloud endpoint is selected, its URL and key
are operator inputs and its privacy/retention policy must be reviewed by the
operator. A completion-only fast route must not be presented as tool-capable.
Hermes is fetched from the pinned upstream release archive and verified by
the SHA-256 in `config/versions.env`; a local private archive is not required
for a public reconstruction.

## Clean-room boundary

`--test-mode --root DIR` rehearses the installer without containers, accounts,
production state, or synthetic users. Full reconstruction additionally needs
private deployment records and canonical backups described in
[`reconstruction.md`](reconstruction.md) and [`backup-restore.md`](backup-restore.md).
Static or synthetic tests do not prove owner-authenticated product behavior.
## Product-level setup

On a fresh host, inspect the first-run plan and then run the setup wizard:

```sh
sudo scripts/hades setup --test-mode
sudo scripts/hades setup --profile standalone --exposure local --yes
```

The setup path asks only for product choices, generates fresh local secrets,
creates the dedicated runtime account, builds the pinned Open WebUI artifact,
installs the pinned Hermes artifact, and writes a private operator-input file.
Use the lower-level operator-input flow below when integrating an existing
deployment or an external model server.
