# Clean reconstruction procedure

The only legitimate deployment inputs are this repository, a private
operator-input file with field semantics in
[`private-input-contract.md`](private-input-contract.md), and documented
component-specific canonical backups. The checked-in
[`config/operator-inputs.env.example`](../config/operator-inputs.env.example)
is the legacy v1 compatibility template; it is not a complete production v2
bundle. Start new v2 installations from
[`config/operator-inputs-v2.env.example`](../config/operator-inputs-v2.env.example),
replace each required placeholder, and keep the filled copy outside Git. The
authoritative pins
are in [`config/versions.env`](../config/versions.env), and the public rebuild
fields and artifact provenance classifications are in
[`config/reconstruction-manifest.json`](../config/reconstruction-manifest.json).
Every runtime-critical artifact is source-controlled, generated from a tracked
template, an explicit operator input, a documented generated secret, restored
canonical state, or an upstream application default; no deployment step relies
on an undocumented pre-existing file.

On a minimal Fedora Cloud or Rocky image without Git, install Git from the
operating system repository before cloning the checkout:

```sh
sudo dnf install -y git
```

This is the source-transfer bootstrap only. The HADES host-preparation script
still plans and installs the remaining pinned runtime prerequisites after the
repository is present.

Keep the checkout at a stable path the `hades-runtime` account can traverse
and read, such as `/opt/hades`. A login user's private home directory can
prevent the Hermes service from starting even when installation itself
succeeds. The installer preflight checks the configured Hermes working
directory before it writes deployment state.

The installer requires at least 8 GiB visible to the guest OS. Allocate 10 GiB
to Fedora Cloud VMs to cover guest kernel and virtualization overhead; assigning
exactly 8 GiB yielded about 7.73 GiB visible and correctly failed preflight.

Run on a supported fresh systemd guest:

```sh
sudo /opt/hades/scripts/prepare-hades-host.sh
sudo /opt/hades/scripts/prepare-hades-host.sh --apply
sudo /opt/hades/scripts/bootstrap-grocy.sh
# Create the protected inputs after Grocy has issued its API key.
sudo /opt/hades/scripts/install-hades.sh --inputs /etc/hades/operator-inputs.env --preflight
sudo /opt/hades/scripts/install-hades.sh --inputs /etc/hades/operator-inputs.env
sudo /opt/hades/scripts/hades-doctor.sh --inputs /etc/hades/operator-inputs.env
sudo /opt/hades/scripts/validate-install.sh --inputs /etc/hades/operator-inputs.env
```

The first host-preparation invocation is plan-only. Apply it only after
confirming that the guest is the intended supported target; it installs the
bounded Docker/Compose, Git, and OpenSSL prerequisites and enables Docker.

The Grocy bootstrap starts only the pinned Grocy service and initializes its
database on the loopback-only listener. Before the full HADES install, sign in
with the upstream first-run account, change its default password, and create an
API key in Grocy's **Manage API keys** page. Save that issued key in the
protected file named by `HADES_GROCY_API_KEY_FILE`. Random text is not a valid
Grocy API key. The bootstrap reuses the same Compose file, named volume, and
network as the canonical installer; it does not reset Grocy state.

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
script never contacts a provider or writes production paths.
`scripts/create-generated-private-inputs.sh` is also **test-only**: it creates
synthetic owner identity, API keys, service passwords, and a dummy model URL
for isolated v2 reconstruction. Its output contains
`HADES_SYNTHETIC_FIXTURE=true`; the normal installer, doctor, and validator
reject that bundle. Do not change the marker or use those generated values for
a real household.

To run the full service composition on a disposable supported guest, authorize
that guest explicitly and keep the synthetic marker intact:

```sh
sudo scripts/authorize-synthetic-deployment-test.sh
sudo scripts/install-hades.sh --inputs /path/to/operator.env --synthetic-deployment-test
sudo scripts/hades-doctor.sh --inputs /path/to/operator.env --synthetic-deployment-test
sudo scripts/validate-install.sh --inputs /path/to/operator.env --synthetic-deployment-test
```

The authorization asks the operator to type the guest's machine ID and writes
a root-owned mode-0600 marker bound to `/etc/machine-id`. The full synthetic
mode requires that marker, v2 generated inputs, and the real host root; it
starts the normal pinned services and runs live doctor/validation checks. Its
install record identifies the machine as test-only. Copying the marker to a
different guest fails. Without the flag and matching marker, synthetic inputs
remain rejected. Never authorize a household or production machine, and
destroy the guest and its synthetic volumes after the rehearsal.

Place the generated bundle under a persistent path whose existing parent
directories allow the `hades-runtime` service account to traverse them. For
example, on the disposable guest prepare a private parent, generate the bundle
as the login user, and keep the output outside a mode-0700 home directory:

```sh
sudo install -d -o "$(id -u)" -g "$(id -g)" -m 0711 /var/lib/hades-synthetic-inputs
scripts/create-generated-private-inputs.sh /var/lib/hades-synthetic-inputs/private \
  --image-ref hades-open-webui@sha256:REPLACE_WITH_BUILT_IMAGE_DIGEST
```

The installer checks that the Hermes runtime can traverse the profile's parent
path before making changes. The generated dummy model endpoint must also be
available during preflight. For an isolated guest, start the tracked
no-provider fixture in a terminal before installation, then stop it after
validation. It serves the synthetic OpenAI-compatible Hermes endpoint and
Hindsight's Ollama-compatible extraction endpoint. The Hindsight route always
returns one fixed test fact and never records the submitted prompt:

```sh
python3 scripts/synthetic-openai-backend.py 0.0.0.0 18080
```

This fixture binds port 18080 for the synthetic deployment rehearsal only; it
is not part of the production stack or a supported household model service.

Production v2 setup sequence:

1. Clone the repository to a stable path such as `/opt/hades`. Install Git
   first if the minimal host image does not include it.
2. Run `sudo scripts/prepare-hades-host.sh` to review the plan, then run it
   again with `--apply` only on the intended guest.
3. Install the pinned Hermes source with
   `sudo scripts/install-hermes-artifact.sh --prefix /opt/hades-hermes`.
   Build the tracked Open WebUI artifact with
   `sudo scripts/build-open-webui-artifact.sh`; copy its immutable
   `HADES_OPEN_WEBUI_IMAGE=...` output into the private input file.
4. Run `sudo scripts/bootstrap-grocy.sh`. Open `http://127.0.0.1:7003`
   locally, or forward it with `ssh -L 7003:127.0.0.1:7003 <user>@<hades-host>`.
   On the first login, change the upstream `admin` / `admin` password
   immediately. In **Manage API keys**, issue a key for HADES. Keep the
   bootstrap listener loopback-only.
5. Save the issued Grocy key in a protected file without putting it in shell
   history or command arguments:

   ```sh
   sudo install -d -m 0700 /etc/hades/secrets/grocy
   sudo install -m 0600 /dev/null /etc/hades/secrets/grocy/api_key
   sudoedit /etc/hades/secrets/grocy/api_key
   ```

   The key must come from this Grocy instance; a random value is not valid.
   Create the SearXNG secret file at the path in the input file with mode
   0600. Keep Hermes and Hindsight API keys only in the protected input/profile
   files.
6. Copy the v2 template to `/etc/hades/operator-inputs.env`, set mode 0600,
   and edit it with `sudoedit`. Use host-reachable and container-reachable
   model URLs, the verified Docker bridge gateway for the Hermes bind address,
   and the exact LLDAP bind password stored in the identity secret file.
7. Create the three LLDAP files (`jwt_secret`, `key_seed`, and
   `admin_password`) under `HADES_IDENTITY_SECRETS_DIR`, each mode 0600 and
   owned by UID 1000.
8. Create `HADES_HERMES_PROFILE/config.yaml` and
   `HADES_HERMES_PROFILE/profiles/hades/config.yaml` from
   `hermes/config.yaml.example`, replacing its example model endpoint with the
   chosen model service. Create `HADES_HERMES_PROFILE/hermes.env` from
   `hermes/env.example`; set `API_SERVER_KEY` and `API_SERVER_HOST` to match
   the protected input file, and retain the repository path, Grocy URL, and
   Grocy key-file path entries. Keep the Hindsight bank template
   `hades-user-{user}` for per-user isolation.
   After the intended owner has completed an authenticated Open WebUI/LDAP
   login, verify that account's LLDAP owner-group membership and exact stable
   Open WebUI subject ID. Put only that ID in the protected operator input's
   `HADES_OWNER_SUBJECT_IDS` field, then rerun the canonical installer so it
   renders the root-owned mode-0640 Hermes owner-policy environment file,
   readable only by the Hermes service group. Leave the field
   empty until that verification; display names and email addresses never
   grant owner policy.
9. Run the installer's non-mutating preflight, install, doctor, and validator
   commands shown above, all with the same protected input file. The installer
   renders the tracked Compose and Hermes service templates during installation
   and checks that the WebUI's LDAP bind password matches the protected LLDAP
   admin password file.

For example, generate file-backed machine secrets without printing the values
or putting them in shell history:

```sh
sudo install -d -o 1000 -g 1000 -m 0700 /etc/hades/secrets/identity
for name in jwt_secret key_seed; do
  sudo sh -c 'umask 077; openssl rand -hex 32 > "$1"' _ "/etc/hades/secrets/identity/$name"
done
sudo install -o 1000 -g 1000 -m 0600 /dev/null /etc/hades/secrets/identity/admin_password
sudoedit /etc/hades/secrets/identity/admin_password
sudo install -d -m 0700 /etc/hades/secrets/grocy /etc/hades/secrets/searxng
sudo install -m 0600 /dev/null /etc/hades/secrets/grocy/api_key
sudoedit /etc/hades/secrets/grocy/api_key
sudo sh -c 'umask 077; openssl rand -hex 32 > "$1"' _ /etc/hades/secrets/searxng/secret_key
```

Choose the LLDAP admin password with a password manager, save it there, and
enter the same value in the protected input file's
`HADES_OPEN_WEBUI_LDAP_APP_PASSWORD` field. Generate Hermes and Hindsight API
keys with a password manager and enter them only in the protected input and
Hermes profile files that consume them. Preflight fails while any
`REQUIRED_` placeholder remains in the production input.

The exact required fields are documented in
[`private-input-contract.md`](private-input-contract.md). The placeholder
`HADES_OWNER_BOOTSTRAP_ID` from older records is not used by current installer
or runtime code; do not rely on it as an identity mapping. The model endpoint
and its container-reachable equivalent must both be verified by the operator.
Never copy a development-home profile or substitute the synthetic generator
for this production setup. Optional owner-gated inputs remain unset unless
their separate policy and credentials are ready.

If a Proxmox environment is available, `scripts/proxmox-bootstrap.sh` is the
optional provisioning handoff. With no `--apply` it only validates inputs and
prints a plan. With explicit `--apply`, it uses an owner-supplied API token to
clone a cloud-init-capable Fedora/Rocky template, configure the requested
guest resources and SSH key, resize the named boot disk, and then hands off to
the guest-local installer. A failed post-clone API call leaves the VM for
inspection; the helper never guesses at cleanup or calls the HADES installer
on the Proxmox host.

Before starting components, the installer creates the shared bridge networks
`hades-application-net`, `hades-private`, and `hades-grocy-net`. It accepts an
existing network only when its driver and scope are `bridge local`; it never
replaces or reconfigures an existing network. The LLDAP Compose record creates
`hades-identity-net` before Open WebUI joins it. Component startup then follows
LLDAP, Open WebUI, Hindsight, Grocy, Agent Zero, SearXNG, the Hermes release
pinned by `config/versions.env`, then the HADES overlay/assets/adapters.
Production migration is
separate: backup, provision, install, restore, validate, owner acceptance,
private-network cutover, and temporary rollback retention.

Decommissioning stops runtime and removes reconstructable material while
preserving `/var/lib/hades` and backups by default. Permanent state destruction
requires a separate, explicit operator action; no destructive uninstall command
is provided.

For a disposable Fedora Cloud 44 libvirt guest, the cloud-init seed must
retain the distribution's default account before applying its SSH key. Keep
`default` first in `users`; an invalid cloud-config can leave the VM booted
but unreachable and make it look like SSH or HADES is at fault. Git is the
only package needed for the initial repository clone; the canonical host
helper installs the remaining HADES prerequisites after the clone:

```yaml
#cloud-config
users:
  - default
  - name: fedora
    ssh_authorized_keys:
      - <disposable-test-host-public-key>
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
packages:
  - git
runcmd:
  - [hostnamectl, set-hostname, hades-clean-guest]
```

Keep only `instance-id` in NoCloud meta-data; do not set `local-hostname`
there. Fedora Cloud's local cloud-init stage can run before the system D-Bus is
available, causing repeated hostname-set warnings and a degraded `cloud-init
status` even though the guest boots. Set the chosen guest hostname with
`hostnamectl` from the late `runcmd` stage instead. Validate the rendered
cloud-config before boot and on the guest with `sudo cloud-init schema
--system`; require `cloud-init status --long` to report no recoverable errors
before counting a clean-host run. Do not put an object under cloud-init's
top-level `user` key; use the distribution-specific `users` entry.

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
Each generated Compose record has an explicit isolated project name and
restart policy so the three synthetic private services cannot collapse into
one Compose project and participate in reboot acceptance.
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

The first full fresh Fedora 44 attempt exposed a packaging defect: Docker's
file-backed Compose secret mounts kept the host `user_tmp_t` SELinux label, so
LLDAP restarted with permission denied while reading its UID-1000 secrets.
The tracked LLDAP contract now uses read-only `:Z` bind mounts, preserving
secret file permissions and SELinux enforcement. The interrupted guest remains
diagnostic evidence and must be rerun from the repaired repository before a
full-stack result is claimed.

That rerun was completed on a fresh Fedora Server 44 cloud guest with an
80-GiB virtual disk, systemd, Fedora Docker/Compose, a loopback model fixture,
and the generated private input bundle. The real privileged preflight passed,
the installer deployed the pinned LLDAP/Grocy/Agent Zero services plus three
isolated synthetic private Compose records and the Hermes unit, and doctor and
validation passed after the normal LLDAP health warm-up. The guest was rebooted
with the operator bundle under persistent storage; all six container groups
and Hermes returned, then doctor and validation passed again. This is
**first-clean synthetic deployment and reboot evidence**. The private records
are intentionally minimal Alpine services, so it does not claim Open WebUI,
Hindsight, SearXNG, or model-backed household behavior.

A second independent fresh Fedora 44 guest was then taken through the same
procedure from a new disk and repository clone. The documented minimal-host
package step supplied `git` (the cloud image did not include it), and the
guest's usable memory was raised to 10 GiB so it exceeded the documented 8 GiB
minimum after host overhead. (The fixture generator now emits those
authoritative immutable Hindsight and SearXNG pins directly; the run recorded
below predates that generator repair.) The generated private bundle was
adjusted only to make its Hindsight and SearXNG records consume the immutable
image pins; real privileged preflight then passed, the installer pulled the
pinned images and completed, and doctor/validation passed. After a guest
reboot, Hermes was enabled and active, all six container groups returned, and
doctor/validation passed after the normal LLDAP health warm-up. This is
**current-HEAD second independent clean synthetic deployment and reboot
evidence**: the generated records now consume immutable image references
directly, without post-generation edits. The private records still use
bounded smoke commands rather than full Open WebUI, Hindsight, SearXNG, and
Hermes application fixtures, so full application reconstruction remains
unproven.

### Full application clean guest B — 2026-09-28

The separate pristine Fedora 44 Guest B completed a real full-stack synthetic
deployment from a cloud image using source
commit `dd17e3716f7fa04060e47259b560dedac92224dd` and an explicit,
machine-authorized synthetic v2 input bundle. It runs the six pinned
application containers (LLDAP, Open WebUI, Hindsight, Grocy, Agent Zero, and
SearXNG) plus the Hermes systemd gateway pinned to 0.21.2. The install marker
records `phase=deployed`; the checkout is clean. After a real guest reboot,
systemd and Docker returned, all six containers returned, Open WebUI and
LLDAP became healthy, and the post-reboot doctor and validator passed.

The guest was rechecked on 2026-09-28: `hades-doctor.sh` passed its structural,
version, secret-mode, service, health, and container checks; `validate-install.sh`
passed its install contract. Both correctly warned that the deployment uses
synthetic identities and needs separate live functional acceptance. All
published application ports are loopback-only; Hermes listens on the private
Docker bridge. No production endpoint is exposed.

This is full application installation and reboot evidence for `dd17e37`, not
an exact-HEAD proof: current HADES HEAD `daa08e1` includes the optional staged
OSINT dynamic-page reader and related manifest/policy changes, plus a
synthetic-only login-fixture helper added after Guest B's install. Guest B has not yet
passed authenticated Alpha/Beta/Gamma household acceptance or a guest-level
backup/destroy/restore drill. It is not owner acceptance, and it does not
close the reconstruction campaign. Preserve this guest as synthetic evidence;
do not destroy it before the missing acceptance work is captured or a clean
successor is available.

#### Synthetic household login fixture

The generated private deployment bundle intentionally contains infrastructure
secrets, not household user passwords. On an explicitly authorized synthetic
guest, `scripts/synthetic-household-identities.py` creates three separate
reconstruction-only LLDAP users, assigns Alpha to `hades-owner` and Beta/Gamma
to `hades-household`, and writes their generated passwords to
`$HADES_STATE_ROOT/acceptance/synthetic-household-credentials.json` as a
root-owned mode-0600 file. It refuses to run without the machine-bound
synthetic-target marker, explicit synthetic v2 inputs, the pinned LLDAP
password helper, or if any of its fixed test IDs already exist. It never
resets the deployment's existing users. Run `--remove` after acceptance to
delete only these fixed test IDs and the credential file. This establishes a
reproducible credential path; it is not itself authenticated application
acceptance and does not clean any Open WebUI rows created by later sign-ins.

On Guest B, the fixture created three accounts without changing its seeded
Administrator/Alpha/Beta/Gamma users. Direct LLDAP login passed for all three,
with distinct subjects and the expected owner/household groups; repeated Alpha
login retained the same subject. The Open WebUI LDAP route also authenticated
each account and returned distinct subjects, but the protected user-info route
returned 401 because new LDAP accounts receive Open WebUI's default `pending`
role. This is an explicit admin-approval gate, not an LLDAP password or group
failure. The seeded prior Alpha account is already the Open WebUI administrator;
its old password is not in the bundle, so no role was elevated and the
protected household flows remain unaccepted. The new accounts and mode-0600
credential file are retained as documented synthetic acceptance fixtures; no
existing password or authority was changed.

## Evidence hierarchy

| Evidence level | Current result | Boundary of the claim |
|---|---|---|
| Static | PASS | Syntax, pins, provenance, policy, CI, and public-safe configuration are validated. |
| Disposable component/fixture | PASS | Read-only domain fixtures, synthetic backup/restore, private-record generation, and test-mode installer contracts pass. |
| First clean machine | PASS for tracked subset | A pristine Fedora system proved the supported-host preflight and tracked LLDAP/Grocy/Agent Zero deployment path. |
| Second independent clean machine | PASS for current-HEAD tracked/synthetic deployment contract | A separate pristine Fedora 44 guest completed current-HEAD real preflight, immutable generated records, deployment, doctor, validation, reboot, post-reboot validation, and owner-style synthetic checks; these private records are minimal service fixtures. |
| Reboot/restart | PASS for tracked subset on two guests | Both disposable Fedora guests recovered the tracked services and enabled Hermes after reboot; private records are bounded smoke services, not full application behavior. |
| Full-stack synthetic clean reconstruction | PARTIAL; Guest C discovery install and reboot pass, independent release proof open | A separate Fedora 44 guest deployed the six pinned application containers and Hermes 0.21.2 from explicit synthetic inputs, passed idempotency with populated state, and recovered after reboot. Basic Alpha conversation persistence, Beta/Gamma private-chat isolation, authenticated Grocy read/write/read-back, component-level Grocy/Hindsight restore, and identity-aware LLDAP/Open WebUI/Hindsight restore with authenticated Hermes recall now exist. Broad household soak, whole-guest restore, and independent Guest B remain open. |
| Actual-image application composition | PASS | `scripts/test-full-application-image-startup.sh` starts the six pinned application images plus a disposable OpenAI-compatible model on an isolated Docker network, creates authenticated synthetic Alpha and Beta users, verifies Alpha model-response persistence and Beta isolation across an Open WebUI container restart, and rejects Beta access to Alpha's chat; no host ports or production state are used. |
| Fresh Fedora 44 full-application attempt | PARTIAL / HISTORICAL | A verified Fedora Cloud 44 guest booted and reached healthy LLDAP/Grocy fixtures, but the attempt stopped while Agent Zero layers stalled at the registry; all temporary guest artifacts were reclaimed. |
| Fresh Rocky 10.2 actual-image composition | PASS | Independent VM 802 installed Docker CE 29.8.1/Compose 5.5.1, built the pinned Open WebUI artifact, started all seven disposable containers, verified Alpha/Beta model and privacy behavior across restart, and cleaned up. |
| Full application clean reconstruction | PARTIAL; Guest C is discovery only, independent release proof open | Rocky 10.2 installed the v2 generated records and all seven services, but that acceptance used Hermes 0.14.0. Guest C proved a full 0.21.2 install and reboot at its then-current source; selected runtime/recovery files from newer local commits have since been copied to it for discovery, so Guest C is not an exact-current-HEAD build. A second pristine release guest, full authenticated household soak, and whole-guest restore remain open. |
| Fresh-install synthetic household soak | PASS for contract/fixture layer | Generated private inputs, test-mode install/doctor/validation, and owner-style authority/multi-user/memory simulations run as one reproducible sequence; no full application behavior is claimed. |
| Fresh-install full application household soak | PARTIAL on Guest C | Authenticated Alpha chat persistence and Beta/Gamma private-chat denial passed; Alpha's chat survived Open WebUI restart and guest reboot. Authenticated Beta recipe feasibility, same-chat shortage confirmation, exact missing-only Grocy list write, same-chat read-back, and post-Grocy-restart fresh-chat read now pass on Guest C. Full memory correction/isolation, broad household workflows, settings, bounded Agent Zero authorization, and a representative household soak remain open on this reconstructed guest. |

The installer-generated full application, household restart/isolation, and
generated-runtime reboot milestones passed on the fresh Rocky guest with the
then-pinned Hermes 0.14.0. Guest B later proved a fresh full application
installation and reboot with Hermes 0.21.2 from source `dd17e37`. Current HADES
HEAD `6b0df12` adds the optional staged OSINT dynamic-page reader and related
manifest/policy wiring, so an exact-current-HEAD guest rebuild remains open.
The broader multi-domain household contract is separately evidenced by the
synthetic household soak, but it has not been run through authenticated Alpha,
Beta, and Gamma sessions on Guest B. Guest-level backup/destroy/restore also
remains open; overall installation/rebuild is still `PARTIAL`.

On 2026-09-16, the actual-image composition was also rerun on the
non-production `hades-core` destination staging guest from HADES revision
`0667aa0`. Its 40-GiB disk accommodated the pinned image set; all seven
disposable containers reached the expected readiness checks, Alpha persistence
and Beta private-chat denial survived an Open WebUI restart, and cleanup
retained no containers or networks. This strengthens destination composition
evidence, but is not a fresh-guest installer run, restored production state,
or cutover acceptance.

The clean Hindsight reconstruction contract uses API port 8888 and control
plane port 9999 inside the image. The generated template now keeps those
listeners distinct; using 9999 for `HINDSIGHT_API_PORT` caused an internal
`EADDRINUSE` collision before the API could start.
The repeatable runtime check is
`scripts/test-hindsight-runtime.sh`; it starts the pinned digest with isolated
state and ephemeral host ports, then verifies both listeners before cleanup.

## Manual-step inventory

| Observed action | Disposition |
|---|---|
| Install Fedora/Rocky host packages and enable Docker | Automated by the plan-first `scripts/prepare-hades-host.sh`; explicit `--apply` remains operator-controlled. |
| Create identity, component-secret, and synthetic private records | Automated by `scripts/create-synthetic-private-fixture.sh`; production values remain explicit operator inputs. |
| Supply the model endpoint and private runtime records | Explicit operator input; no value is inferred from the seasoned machine. |
| Set secret modes/ownership and SELinux labeling | Fixture generator or operator supplies modes/ownership; installer validates them, and the Compose contract applies the SELinux relabel. |
| Start services in dependency order and enable Hermes | Installer; no shell-history restart sequence is required. |
| Restore canonical application state | Not performed for the minimal synthetic guest; requires documented component backups and remains part of the full-application milestone. |

## Guest C discovery build A — current-HEAD caveat

Guest `hades-v1-clean-guest-c-20260928` is a separate Fedora 44 Cloud guest
from the verified Fedora image (SHA-256
`28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f`), with
4 vCPU, 10 GiB RAM, an 80-GiB virtual disk, systemd, Docker, and SELinux.
Its clean `/opt/hades` checkout was advanced to committed source
`2beb031407ebb4bf16cdb4e0c4d944f414256545` through a local Git bundle. The
documented synthetic private-input generator and machine-bound test target
authorization supplied its only private inputs. The canonical installer
deployed LLDAP, Open WebUI, Hindsight, Grocy, Agent Zero, SearXNG, and Hermes
0.21.2; all immutable image pulls completed. The full install passed again
after the source fast-forward.

The read-only doctor and install validator pass with their expected warnings
for synthetic identities and separate functional acceptance. An installer
rerun after creating synthetic Alpha/Beta/Gamma identities and persisting an
Alpha chat preserved all six container IDs, eight network IDs, and 2,964
hashed persistent files byte-for-byte. Open WebUI survived its own restart;
Alpha's marker chat remained available and Beta was denied. A full guest reboot
returned Docker and Hermes automatically, all six containers became healthy,
doctor/validator passed at steady state, and Alpha's chat persisted while Beta
remained denied.

Guest C exposed two fixture gaps that were repaired in `2beb031`: a pristine
LLDAP instance has only its built-in groups, so the synthetic login helper now
creates missing `hades-owner`/`hades-household` groups and records only the
groups it owns for guarded cleanup; and the synthetic OpenAI backend now emits
valid streamed function-call deltas. A focused test covers text and tool-call
SSE, and the clean-reconstruction test plus an authenticated guest pantry call
pass. Open WebUI gave the first synthetic Alpha account its expected bootstrap
admin role; Beta and Gamma initially received `pending` and were explicitly
approved as ordinary synthetic users. No existing user or production role was
changed.

This is discovery build A, not the independent release proof. Its authenticated
coverage remains partial: no full memory retain/recall/correction, canonical
Grocy mutation/recipe, search failure-honesty, settings isolation, bounded
Agent Zero authorization, or backup/destroy/restore soak has passed on this
guest. The guest still contains documented synthetic accounts, state, and
credentials and must be preserved until the remaining discovery work is
captured; a separate pristine guest is required for build B.

### Guest C current-source integration-path follow-up — 2026-09-28

At this checkpoint Guest C was at committed source `74f206f4dbcda3e6e542fa01cab8beff25122126`;
its installed Hermes overlay matched the committed source SHA-256
`012e5913b30728dc629707e024ba8ff51fcf2fc7b24356c9b8c9072ce99165a0`.
Authenticated Alpha dogfood found the public-research privacy module was
present in the checkout but not discoverable from the generated private
overlay path when `HADES_INTEGRATIONS_ROOT` was empty. Commit `74f206f` fixes
lookup through Hermes' working directory and adds a non-mutating doctor check.
The canonical installer reran successfully on Guest C; doctor and validator
pass with their expected synthetic-mode warnings.

After that reinstall, authenticated Alpha UI returned SearXNG snippets for an
ordinary public documentation query, gave an honest unavailable response when
the Guest C SearXNG container was stopped, and refused a synthetic private-
person request without citations. SearXNG was restarted and all six application
containers plus Hermes were active. This closes only the tested search path and
policy lookup gap. Later discovery work copied selected files from newer local
commits into Guest C, so the guest no longer represents an exact-HEAD install.

### Guest C Grocy composition and component recovery — 2026-09-29

Guest C's Git checkout remains at `74f206f4dbcda3e6e542fa01cab8beff25122126`.
For discovery only, the current Hermes overlay, systemd template, doctor,
validator, and recovery scripts were copied from later local source commits.
The canonical installer reran with the guest's explicit synthetic bundle;
doctor and validator passed from `/home/fedora`, including the functional
Grocy MCP read probe. This is not a clean reconstruction build or an
undocumented-intervention-free release rehearsal.

Authenticated synthetic Alpha UI exercised the current Grocy catalog on the
guest: pantry returned canonical empty stock; one explicit shopping-list add
returned Grocy's successful item result; a fresh HADES turn read the item back
from Grocy. The product/list fixture remains synthetic and is retained for the
restore check.

The backup rehearsal exposed and repaired two portable-state issues. Guest C
uses the container name `hades-lldap`, while the backup helper assumed
`hades-lldap-production`; Fedora also lacks the host `sqlite3` CLI. The helper
now accepts `HADES_LLDAP_CONTAINER`, uses Python's standard-library SQLite
online backup and immutable integrity-check APIs, and validates snapshots
without creating SQLite sidecars. Guest C produced and validated a mode-0600,
checksummed four-database snapshot for Open WebUI, LLDAP, Grocy, and Hermes.
`scripts/test-grocy-backup-restore.sh` restored the Grocy database into a fresh
digest-pinned `--network none` container with no published port and confirmed
the synthetic shopping-list marker through Grocy's authenticated API; the test
container and volume were removed.

The tracked native Hindsight destroy/restore test also passed on Guest C using
separate temporary source and restore volumes plus the synthetic extractor:
the source volume was destroyed, the native archive restored into a fresh
volume, and health, memory-list, and recall checks passed. It never read the
Guest C live Hindsight volume. These are component-level results, not a full
application recovery. LLDAP/Open WebUI subject mapping after restore, complete
Hindsight data backup, Agent Zero/SearXNG state, full guest destroy/restore,
household soak, and independent pristine Guest B remain open. Guest C remains
discovery build A; production was not changed.

A subsequent read-only check of Guest C found a healthy Hindsight service but
an empty bank collection, despite the earlier checkpointed Alpha UI
retain/recall. The disposable authenticated-memory harness had pre-created its
banks, masking the clean-volume case. The tracked explicit-memory path now
creates a missing owner or household bank from the trusted session scope and
subject before retaining or recalling; it never accepts a bank identifier
from model output. The authenticated UI acceptance now has a mode that skips
bank precreation. On a fresh disposable Hindsight volume, that mode passed
retain, correction, fresh-conversation recall, cross-user isolation, and chat
persistence.

Guest C then exposed a second defect: Open WebUI's persisted
`openai.api_configs` was empty, so it did not send the authenticated stable
subject header to Hermes. The deployment template now seeds
`X-Hermes-Session-Key: hades-user-{{USER_ID}}`; the fresh-volume UI test checks
that seeded config and passes the memory acceptance above. `hades-doctor`
checks the persisted header. After updating Guest C's synthetic Open WebUI
config through its admin API, Alpha retain and fresh-conversation recall
passed; canonical recall from Alpha's exact subject bank returned the marker. A canonical
installer rerun, doctor, and validator also passed on C. C remains a
contaminated discovery guest; identity-aware full restore and independent
pristine Guest B remain open. Production was not changed.

Guest C then exposed first-login and model-visibility gates for household
members. New LLDAP users arrived in Open WebUI with role `pending`, and the
ordinary-user model catalog was empty. After verifying Beta and Gamma's
`hades-household` membership in LLDAP, synthetic Alpha admin promoted those
accounts to ordinary `user` and granted each read access to `hermes-agent`.
Both LDAP sessions then saw the HADES model. Authenticated Guest C UI
acceptance passed Alpha retain/correction/fresh recall and Beta/Gamma memory
isolation. The refreshed SQLite snapshot contains Alpha/Beta/Gamma roles,
19 conversation records, the stable-subject header, and the two per-user model
grants. The latest SQLite snapshot and matching native Hindsight archive were
then restored together into isolated LLDAP, Open WebUI, and Hindsight
containers. LDAP authentication for Alpha, Beta, and Gamma returned the same
Open WebUI subject IDs and roles; each account saw the archived `hermes-agent`
model. The restored Hermes 0.21.2 gateway used the tracked HADES overlay and
the guest's actual operator configuration, with no synthetic owner-subject
override. Authenticated HADES chat returned only corrected pear for Alpha's
typo-form recall; Beta and Gamma received no matching private memory. The raw
Alpha archive still contains historical mango and pear records. Restored chat
histories were readable by their matching accounts, and an Alpha-only setting
survived an Open WebUI restart without changing Beta. This is an identity-aware
restore of LLDAP, Open WebUI, Hindsight, and Grocy, not a whole-HADES restore.
The pinned Grocy container returned the restored `HADES Synthetic Milk`
shopping-list row with quantity 1 through its authenticated API. Authenticated
Beta chat also returned it through HADES's direct read-only Grocy route. This
did not call the Grocy MCP tool or perform a mutation. Agent Zero, SearXNG,
guest boot, and a destroy/restore cycle remain untested. The disposable target
was removed; Guest C and production were not changed by the replay.

### Guest C declared Grocy inputs and current-turn routing — 2026-09-29

An authenticated Beta UI attempt on discovery Guest C initially fell through
to the synthetic model because the direct HADES Grocy routes did not resolve
the documented `HADES_GROCY_API_KEY_FILE` and `HADES_GROCY_URL` inputs. Shared
resolvers now honor those generated private inputs as well as the legacy
`GROCY_*` runtime names (`b5f7a75`). The same attempt also exposed a stale
intent ordering issue: an older recipe question in the same chat could
override the current shared-shopping-list read. Current list reads now run
before that historical recipe fallback (`7323d86`).

The focused Hermes runtime contract passes with only the documented HADES
private-input variables set, including the stale-recipe/current-list
regression. On Guest C the updated overlay was installed by rerunning the
canonical installer with the explicit synthetic input bundle; its hash
matches the local source. Doctor and install validation pass. Authenticated
synthetic Beta checked a uniquely named saved recipe, saw exactly two missing
pieces, confirmed the same-chat offer, and received confirmation that only
those missing pieces were added. The canonical Grocy API showed one test row
at quantity 2, the preexisting milk row unchanged at quantity 1, and no stock
mutation. The same chat then read the list correctly; after restarting Grocy,
a fresh Beta chat also read the persisted shared list correctly. Test
recipe/product/ingredient/list rows and
the uniquely titled test chats were removed; final Grocy state returned to
the single original milk list row with no saved test recipe or stock.

Guest C remains a contaminated discovery target with an older checkout and
selected source copied forward; this is not independent clean-install proof.
Whole-guest restore, broader household soak, and pristine independent Guest B
remain open. Production was not changed.

### Guest C Agent Zero and SearXNG component recovery — 2026-09-29

The actual generated Guest C mounts were inspected without reading workspace
or settings contents. A stopped Agent Zero workspace was archived with a
protected temporary artifact, restored to a new volume, and launched with the
pinned image in an isolated, unpublished container; its UI returned HTTP 200.
The rehearsal found the upstream-created `/a0/usr/.env` at mode `0644`, even
though the file contains secrets. The installer now enforces mode `0600`, and
doctor plus install validation check it without changing host state. Rerunning
the canonical installer on Guest C corrected the file to root-owned `0600`;
doctor and validator both pass. CI covers the mode correction without
disclosing test secret material.

SearXNG's generated `/etc/searxng` state was independently archived and
restored into a fresh volume. With the same explicit read-only settings input
and pinned image, the private test instance returned JSON search HTTP 200 with
two results and published no host port. All temporary restore artifacts were
removed. Agent Zero delegation was not tested because no disposable model
backend was configured. Neither component drill proves complete HADES restore,
Guest B, off-host backup custody, or production acceptance.

### Guest B first-boot cloud-init warning — 2026-09-29

The first current-source Guest B candidate was created from the signed Fedora
44 base image on the private NAT network, but its NoCloud metadata supplied
`local-hostname`. Fedora Cloud ran `hostnamectl` during cloud-init's local
stage before the system D-Bus was available. The VM became reachable and the
hostname was present, but `cloud-init status --long` reported recoverable
hostname warnings and returned status 2. This candidate is discovery-only and
does not count as a clean build. The documented seed now omits `local-hostname`
and sets the hostname from the late `runcmd` stage; the revised cloud-config
passes Fedora 44's schema validator. Rebuild from the signed base image before
continuing acceptance; do not repair this guest manually and count it as clean.
