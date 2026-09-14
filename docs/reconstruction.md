# Clean reconstruction procedure

The only legitimate deployment inputs are this repository, an operator-input
file based on [`config/operator-inputs.env.example`](../config/operator-inputs.env.example),
with field semantics in [`private-input-contract.md`](private-input-contract.md),
and documented component-specific canonical backups. The authoritative pins
are in [`config/versions.env`](../config/versions.env), and the public rebuild
fields and artifact provenance classifications are in
[`config/reconstruction-manifest.json`](../config/reconstruction-manifest.json).
Every runtime-critical artifact is source-controlled, generated from a tracked
template, an explicit operator input, a documented generated secret, restored
canonical state, or an upstream application default; no deployment step relies
on an undocumented pre-existing file.

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
opt-in and are never enabled by the production path. The read-only doctor
returns nonzero when tracked runtime checks or Compose validation fail; missing
optional live checks remain warnings.

For a disposable supported-host rehearsal, create the four explicit private
records and their synthetic file-backed inputs with
`scripts/create-synthetic-private-fixture.sh /absolute/fixture/path`. The
script never contacts a provider or writes production paths; start an approved
loopback model fixture separately, then pass the generated `operator.env` to
the installer. This keeps the full-install rehearsal reproducible without
copying private deployment records into the repository.

If a Proxmox environment is available, `scripts/proxmox-bootstrap.sh` is the
optional provisioning handoff. With no `--apply` it only validates inputs and
prints a plan. With explicit `--apply`, it uses an owner-supplied API token to
clone a cloud-init-capable Fedora/Rocky template, configure the requested
guest resources and SSH key, resize the named boot disk, and then hands off to
the guest-local installer. A failed post-clone API call leaves the VM for
inspection; the helper never guesses at cleanup or calls the HADES installer
on the Proxmox host.

Deployment order is LLDAP, Open WebUI, Hindsight, Grocy, Agent Zero, SearXNG,
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
evidence level is full-stack reconstruction with those explicit records and
canonical synthetic backups on independent guests.

A second pristine Fedora 44 x86_64 KVM guest independently reran the
credential-free reconstruction contract, synthetic backup/identity restore,
missing-input non-mutation contract, private-input lifecycle contract, and
authoritative version-manifest contract. All passed. This strengthens the
portable static/disposable evidence but still does not claim a full HADES
reconstruction because the private runtime records were intentionally not
copied into the guest.

The private-record setup is now reproducible from repository state:
`scripts/create-synthetic-private-fixture.sh` creates the four mode-restricted
deployment records, identity files, referenced component secrets, and an
explicit operator input file under a caller-selected disposable directory.
This removes the former ad-hoc fixture construction from the next independent
full-install rehearsal; it remains synthetic evidence and does not replace
owner-private deployment records.

The first disposable guest also ran the installer in real privileged
`--preflight` mode with non-secret synthetic identity files and four valid
minimal private deployment records. Fedora/Docker/systemd, disk, port,
ownership, and record syntax checks passed; the install marker and target state
were absent afterward. This proves the complete pre-mutation gate on a
supported host without deploying or copying production material.

Using the same disposable guest, the real installer then completed against
minimal safe Compose records and a restart-capable synthetic Hermes unit. The
tracked services remained running, the Hermes unit was enabled and active, the
install marker reached `phase=deployed`, and both validator and doctor passed
when invoked by absolute path from outside the repository. This exercise
exposed and repaired repository-relative compose discovery and missing export
of the LLDAP secret-directory input.

That fixture was then changed to reference its synthetic image through an
additional variable in the operator input file. Installer, validator, and
doctor all passed from `/tmp`, proving private Compose interpolation does not
depend on the caller's environment or working directory.

The real preflight fixture also served a disposable loopback HTTP endpoint for
the configured model URL. The bounded reachability probe passed and the
preflight remained non-mutating; an unreachable endpoint now fails clearly
before any target directory is created.

The synthetic full deployment path also verifies that every supplied private
Compose record has at least one running service before the installer writes
`phase=deployed`; tracked containers and the enabled Hermes unit are checked
at the same boundary. Private Compose records using an unpinned `latest` image
are rejected during preflight, and all four private records must be mode 0600
or 0640. The installed Hermes unit is mode 0600.

After installation, the same guest was rebooted. Systemd returned to
`running`, Docker restarted Agent Zero, Grocy, and LLDAP automatically, and
LLDAP returned `healthy` after its normal startup interval. This is reboot
evidence for the tracked subset only; it is not evidence that missing private
services or Hermes recovered.

The credential-free synthetic backup drill in
`scripts/test-synthetic-backup-restore.sh` creates Alpha/Beta identities,
subject-scoped memory, a conversation marker, and Grocy stock; it destroys the
source state and restores into a separate target. Stable subject IDs, memory
banks, private markers, and canonical stock pass integrity checks. This proves
local restore mechanics only, not encrypted off-host custody or owner-state
recovery.

The reconstruction contract also exercises an explicit test-only interruption
after preparation. A rerun preserves a persistent state marker, revalidates
the private records and secret metadata, and reaches the normal prepared
phase without duplicate or destructive cleanup. Invalid private Compose,
unpinned image, and unsafe-secret-permission inputs fail before the sandbox is
mutated. This is partial-install evidence; it does not substitute for a
privileged deployment interrupted during live service startup.

## Evidence hierarchy

| Evidence level | Current result | Boundary of the claim |
|---|---|---|
| Static | PASS | Syntax, pins, provenance, policy, CI, and public-safe configuration are validated. |
| Disposable component/fixture | PASS | Read-only domain fixtures, synthetic backup/restore, private-record generation, and test-mode installer contracts pass. |
| First clean machine | PASS for tracked subset | A pristine Fedora system proved the supported-host preflight and tracked LLDAP/Grocy/Agent Zero deployment path. |
| Second independent clean machine | PASS for credential-free contract | A separate pristine guest reran the static/test-mode reconstruction and restore contracts; private full-stack records were not deployed there. |
| Reboot/restart | PASS for tracked subset | The first disposable guest recovered its tracked services after reboot; missing private services are not included in this claim. |
| Full-stack clean reconstruction | NOT PROVEN | Requires one fresh supported systemd guest with the generated private records and synthetic canonical backups. |
| Fresh-install household soak | NOT PROVEN | Follows a successful full-stack reconstruction and exercises the reconstructed HADES application path. |

The exact remaining external milestone is therefore **one clean supported
systemd VM** on which the full explicit-input deployment completes. Until that
evidence exists, installation/rebuild remains `PARTIAL` in the stable-v1 map.
