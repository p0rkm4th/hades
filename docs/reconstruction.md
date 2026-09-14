# Clean reconstruction procedure

The only legitimate deployment inputs are this repository, an operator-input
file based on [`config/operator-inputs.env.example`](../config/operator-inputs.env.example),
and documented component-specific canonical backups. The authoritative pins
are in [`config/versions.env`](../config/versions.env).

Run on a supported fresh systemd guest:

```sh
sudo /opt/hades/scripts/install-hades.sh --inputs /etc/hades/operator-inputs.env --preflight
sudo /opt/hades/scripts/install-hades.sh --inputs /etc/hades/operator-inputs.env
sudo /opt/hades/scripts/hades-doctor.sh --inputs /etc/hades/operator-inputs.env
sudo /opt/hades/scripts/validate-install.sh --inputs /etc/hades/operator-inputs.env
```

The installer is safe to rerun and preserves state, stable identities, and
operator secrets. It requires the four private runtime records named in the
input template (three Compose records and one Hermes systemd unit), validates
all of them before deployment, and starts them in dependency order.
`--test-mode --root DIR` performs a credential-free contract rehearsal and
creates no containers or synthetic production data. Synthetic fixtures are
opt-in and are never enabled by the production path.

Deployment order is LLDAP, Open WebUI, Hindsight, Grocy, SearXNG, Agent Zero,
Hermes 0.14.0, then the HADES overlay/assets/adapters. Production migration is
separate: backup, provision, install, restore, validate, owner acceptance,
private-network cutover, and temporary rollback retention.

Decommissioning stops runtime and removes reconstructable material while
preserving `/var/lib/hades` and backups by default. Permanent state destruction
requires a separate, explicit operator action; no destructive uninstall command
is provided.

## Evidence record

Static and disposable test-mode checks pass. A first clean Fedora 44 KVM guest
was booted from the public cloud image with systemd, networking, Docker, and
Compose. After explicit synthetic identity inputs were supplied, the tracked
LLDAP, Grocy, and Agent Zero subset installed and was safely rerun: LLDAP
became healthy, Grocy remained running, and Agent Zero's bundled workers
stabilized. The run exposed and repaired secret ownership, upstream Agent Zero
startup writes, internal `SETUID`/`SETGID` needs, private-record validation
order, and owned-port idempotency.

This is **first-clean-machine / tracked-subset evidence**, not a full HADES
reconstruction pass. The guest did not contain the four required private
Open WebUI, Hindsight, SearXNG, and Hermes deployment records, so no full
conversation, memory, search, or Hermes acceptance is claimed. The next
evidence level is a second independent guest using those explicit records and
canonical synthetic backups.
