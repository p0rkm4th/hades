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
operator secrets. `--test-mode --root DIR` performs a credential-free contract
rehearsal and creates no containers or synthetic production data. Synthetic
fixtures are opt-in and are never enabled by the production path.

Deployment order is LLDAP, Open WebUI, Hindsight, Grocy, SearXNG, Agent Zero,
Hermes 0.14.0, then the HADES overlay/assets/adapters. Production migration is
separate: backup, provision, install, restore, validate, owner acceptance,
private-network cutover, and temporary rollback retention.

Decommissioning stops runtime and removes reconstructable material while
preserving `/var/lib/hades` and backups by default. Permanent state destruction
requires a separate, explicit operator action; no destructive uninstall command
is provided.
