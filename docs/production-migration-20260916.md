# Production migration checkpoint — 2026-09-16

This is an in-progress migration record. Laptop production remains enabled and
is the rollback source; no hostname cutover or laptop cleanup has occurred.

## Destination

The current destination is Erebus VM 802 (`hades-core`, `<destination-ip>`),
selected because it has 90 GiB storage and 12 GiB RAM. The earlier
`hades-fresh-reconstruction` label is retained only in historical acceptance
records.
VM 800 remains a smaller staging guest and is not being used as the production
target.

The destination currently runs the migrated application stack:

- Open WebUI, using the transferred `0.11.5` HADES image digest
- Hermes, using the restored `hades` profile
- LLDAP, using the restored production directory database and identity files
- Hindsight, using the restored production state
- Grocy, using the restored production state
- SearXNG and Agent Zero, using the restored production volumes/configuration

The synthetic destination state was preserved under timestamped staging names
before replacement. The source migration package is retained in the private
operator migration directory and includes full Open WebUI and Grocy state
archives, full LLDAP data plus a protected secret archive, SQLite snapshots,
the protected Hindsight export, Hermes profile, identity material, deployment
source, versions, and selected Agent Zero/SearXNG artifacts. LLDAP secret
encryption and full Agent Zero encrypted custody remain pending. Alexandra also
holds current complete-history Git bundles for HADES revision `665234f` (with
the earlier `b653825`, `64977c3`, `ef630ac`, and `fb5190d` checkpoints retained)
and the infrastructure repository checkpoint `9bfffcf`, each with a verified
`SHA256SUMS` file.

Rollback custody is:

```text
host: Alexandra (`<rollback-host>`)
path: /srv/hades-backups/manifests/migration-20260916/
restore order: identity -> Open WebUI -> Hindsight -> Grocy -> Hermes -> Agent Zero/SearXNG
source runtime: laptop, retained and not disabled
```

The Git bundles can reconstruct tracked source independently of the laptop.
The private package contains the data archives and operator inputs; its exact
contents and checksums remain outside Git.

The current production Hindsight state is now represented by a protected
custom-format PostgreSQL export on Alexandra. Its archive structure and
checksum were verified, and the export restored successfully into a uniquely
named temporary database with 91 catalog tables before that temporary database
was dropped. The canonical Hindsight database was not modified. This closes
the Hindsight component backup/restore gate; the full all-component service
restore and encrypted off-host custody remain separate requirements.

The refreshed `hades-665234f.bundle` and `hades-infra-9bfffcf.bundle` are
independently checksum-verified on Alexandra. Alexandra does not currently
have the `git` executable, so semantic
bundle verification was performed on the source workstation before transfer;
the backup host verified the transferred bytes and manifest.

On 2026-09-16, Alexandra independently verified the portable archive
checksum manifest, verified both Git bundles, extracted all six volume
archives into a protected rehearsal directory, and passed SQLite integrity
checks for the four SQLite snapshots. The rehearsal did not touch any live
runtime or production data.

## Checks completed

- Fresh source SQLite snapshots passed integrity checks for Open WebUI,
  LLDAP, Grocy, and Hermes.
- All six source application containers were briefly quiesced for full-volume
  archives and restarted afterward.
- Destination Open WebUI retained 3 users and 25 chats across a restart.
- Destination Open WebUI, Grocy, Hindsight, and SearXNG returned healthy HTTP
  responses; LLDAP and Open WebUI reached healthy container state.
- Hermes returned HTTP 200 for `/health` and `/v1/models` after correcting the
  restored laptop-specific Docker bridge bind address.
- Hermes completed an authenticated chat completion after the destination
  profile was placed in the nested `-p hades` profile path and its model
  selector was redirected to the bridge-only temporary model endpoint.
- Open WebUI and Hindsight can reach Hermes and the bridge-only temporary model
  endpoint from their containers. The temporary model is bound to the Docker
  bridge, not the LAN.
- Grocy's API and SearXNG JSON search returned HTTP 200.

After the Erebus VM reboot, the manually launched synthetic inference backend
was found stopped. It was replaced with two named Docker containers on VM 802:
`hades-synthetic-model-loopback` (`127.0.0.1:18080`) and
`hades-synthetic-model-bridge` (`<docker-bridge-ip>:18080`). Both use the tracked
`synthetic-openai-backend.py` fixture and `restart: unless-stopped` semantics.
Post-restart checks passed for the loopback model list, authenticated Hermes
model listing, container-to-Hermes reachability, and an authenticated chat
completion. This remains a temporary inference fixture; it is not a final
model-placement decision.

After the Agent Zero restore was repaired by correcting the migrated `.env`
ownership to container-root/0600, the destination host became unreachable
(`the Proxmox host and destination VM both timed out`). The laptop
production stack and Alexandra remained outside that event. Destination
post-repair acceptance must be resumed after Erebus returns; no cutover was
attempted.

The resumed profile audit found laptop-specific workstation-local paths in the
active Hermes configuration. The destination now has the verified
`hades-infra` checkout at revision `50a56c5`, the pinned Grocy MCP `0.2.0`
runtime, and destination-local paths in both active profile copies. Hermes
restarted with the Grocy MCP child process and passed authenticated health,
model-list, and chat checks afterward. The read-only Proxmox/NetBox token files
were then transferred from the protected operator inputs with matching
per-file checksums and restrictive permissions. Destination probes authenticated
successfully to both Proxmox nodes and NetBox; the configured Uptime Kuma status
endpoints also returned HTTP 200. No credentials or privileges were fabricated.
Chromium is not installed on the destination, so browser-engine workflows
remain distinct from the SearXNG web-search path and are not claimed as passed.

The destination checkout was one revision behind the current read-only
homelab adapter and still used an obsolete Kuma HTML status path. Only the
adapter Python files were refreshed, with the prior destination directory
retained as a rollback copy. The composed adapter then returned `OK` from
Proxmox, NetBox, Kuma, and the capability matrix. Installing the explicitly
required `nmap` package enabled a bounded current-LAN discovery scan
through the adapter; it returned 10 transient host observations and performed
no inventory writes.

The adapter's owner-snapshot contract also returned `OK` and explicitly
reported `read_only=true` and `writes_performed=false`. It identified only
Alexandra and Erebus as currently online from Proxmox; NetBox-only hosts such
as Hermes, Hypnos, Tartarus, and Thanatos remained inventory-only rather than
being promoted to live status.

The control-plane source-of-truth audit found two destination-inventory gaps:
Proxmox sees VM 802, but the current NetBox seed contains only the seven
physical/observed records and no VM 802 intended-inventory record; Kuma's
published page contains 11 existing monitors and does not yet include VM 802
or Open WebUI. Plan-only NetBox and Kuma updates are recorded in the private
infrastructure repository and remain unapplied until the destination address
reservation is authoritative. HADES has no write authority to either system.

The pre-cutover LAN reachability audit found Open WebUI bound only to VM
loopback. The destination compose environment now binds it specifically to
`<destination-ip>:3000`; the migrated data volume was preserved, and the LAN
health endpoint returned HTTP 200 after restart. This prepares client
verification without changing `hades.local` or laptop routing.

After the binding change, Open WebUI returned to healthy state with the
migrated SQLite database intact: 3 users, 25 chats, and `integrity_check=ok`.

The LAN exposure audit found only SSH, Cockpit, and the intended Open WebUI
port reachable from the client network. Grocy, Agent Zero, SearXNG, Hindsight,
Hermes, and both synthetic model bindings remain loopback- or Docker-bridge
scoped.

The name audit still finds no `hades.local` resolution or mDNS advertiser, and
VM 802 currently receives a DHCP address. The remaining network
cutover contract is therefore a stable DHCP/DNS reservation (or an explicitly
approved equivalent) plus owner-side resolution verification; the temporary
address is not being treated as canonical.

A per-request client simulation using `hades.local` mapped to the current VM
address returned HTTP 200 from Open WebUI, confirming the application path
itself is ready once the authoritative name resolves.

The repository now includes `scripts/production-cutover-preflight.sh`, a
read-only fail-closed gate for the final change window. It checks destination
identity, exact authoritative source revision and clean checkout state,
and verifies that the active `hades-hermes.service` working directory is that
same verified destination checkout,
container persistence, VM `onboot`, LAN health, simulated and authoritative
`hades.local` routing, protected Alexandra rollback custody, and preservation
of the laptop source runtime. The source revision is supplied explicitly by
the operator; a dirty or detached destination checkout cannot pass this gate.

Before invoking this preflight, the operator must supply the destination
repository path through `HADES_DESTINATION_REPO` and the expected full Git
revision through `HADES_DESTINATION_SOURCE_REVISION`, alongside the existing
destination, rollback, and Proxmox inputs. The repository path is intentionally
an operator input rather than a tracked host-specific default.

The protected rollback inputs are explicit as well: set
`HADES_ROLLBACK_PACKAGE_ROOT` to the Alexandra package root and
`HADES_ROLLBACK_ROOT` to its migration subtree; the preflight and final
verifier validate both the package-level and repository-level checksum sets.
The final verifier also requires `HADES_DESTINATION_SSH` for a read-only
hostname check and accepts `HADES_DESTINATION_HOSTNAME` (defaulting to
`hades-core`) as the expected guest identity.
The final verifier additionally requires
`HADES_LAPTOP_CLEANUP_RECORD` pointing to the completed, secret-free
decommission evidence record.

Reservation inputs for the authoritative LAN layer are: VM 802 guest MAC,
current DHCP address, intended hostname `hades.local`,
and intended service port `3000`.

The laptop resolver is Tailscale-managed (`100.100.100.100`), and direct
queries to the observed LAN gateway addresses did not return a usable
`hades.local` record. DNS/reservation ownership therefore remains outside the
HADES VM and must be changed at the authoritative LAN/DNS layer before the
normal client path can be switched.

VM 802 and its guest hostname were promoted from the temporary
`hades-fresh-reconstruction` identity to `hades-core`. Hermes and all migrated
containers remained active through the identity change; this is an internal
destination promotion, not a DNS or client cutover.

The guest DHCP profile now requests the FQDN `hades-core.attlocal.net` on
future lease renewal. The current lease remained active;
this does not substitute for an authoritative reservation or the required
`hades.local` record.

## Acceptance defect

The preserved `owner_initial_password` artifact did not authenticate the
migrated owner account through Open WebUI (`/api/v1/auths/signin` returned
HTTP 400). This is not being “fixed” by trying unrelated passwords or
resetting the existing owner account. The exact current owner authentication
material and the owner-visible acceptance session remain required before
cutover.

## Not yet done

- owner login and owner-visible chat/memory/Grocy/web acceptance
- `hades.local` cutover and private client verification
- full all-component live application rollback rehearsal on Alexandra (individual
  artifact and component restore checks exist; an end-to-end service-level
  restore still requires an isolated runtime target)
- laptop production shutdown and cleanup

The destination VM is currently reachable again, and all
six migrated containers plus Hermes are running after the reboot. The owner
authentication defect and all cutover gates above remain open.

## Source/runtime staging checkpoint — 2026-09-17

The clean `b102dfd` candidate was promoted as the Hermes systemd service
working directory on VM 802 after verifying its full revision and clean tree.
The prior service unit was preserved in a protected rollback directory with a
checksum. Hermes restarted successfully, its private Docker-bridge health
endpoint returned HTTP 200, and all six migrated application containers
remained running. A bounded authenticated Hermes model request also returned
non-empty content from the advertised `hermes-agent` model. This is a
reversible source/runtime staging change only;
owner acceptance, authoritative `hades.local` routing, laptop shutdown, and
cleanup were not performed.

The repeatable form is
`HADES_MODEL_SMOKE_CONFIRM=1 scripts/destination-hermes-model-smoke.sh` with
the destination SSH target and protected Hermes profile path. It prints only
the model identifier and response length; the service key and response body
are never emitted. Its contract and destination run both pass.

The staged source rollback is now an explicit operator command:
`scripts/rollback-destination-hermes-source.sh`. It requires
`HADES_ROLLBACK_CONFIRM=1`, the destination SSH target, the protected rollback
directory, the candidate path and full revision, and the prior service working
directory. Before changing the unit it verifies the candidate is clean, the
preserved unit checksum, and the expected prior path; it restores the staged
unit automatically if the rollback restart fails. The command was contract
tested but not invoked.

The cutover preflight treats protected, checksum-verified LLDAP and Agent Zero
archives as sufficient for the independent rollback requirement while
reporting their long-term encryption custody as a separate pending owner gate.

VM 802 is configured with `onboot=1` on Erebus so the destination application
stack is not dependent on manual VM startup after a Proxmox host reboot.
Hermes is enabled under systemd, and all eight destination containers report
`restart=unless-stopped` while running.

The latest private revalidation found Hermes enabled/active, Open WebUI
healthy on the destination LAN address, Hindsight and SearXNG responding, the
bridge-scoped synthetic model exposing one model, and an authenticated Hermes
chat completion returning HTTP 200. The direct unauthenticated Grocy probe
returned HTTP 401, which is the expected protected-service response. Hermes
remains intentionally reachable to its private container clients through the
Docker bridge rather than through a host-wide listener.

## Destination checkout drift — 2026-09-17

A read-only inspection of VM 802 found the destination checkout
checkout detached at `c3f7262`, an ancestor of authoritative HADES `e280ed6`,
with ten modified tracked files and an untracked pre-migration directory. The
active `hades-hermes.service` uses that checkout as its working
directory while executing `/opt/hades-hermes`. This state is preserved and
must be reconciled or explicitly frozen in a controlled change before owner
acceptance; no dirty destination files were discarded or overwritten. Evidence
is in
[`destination-repository-drift-2026-09-17.txt`](../acceptance/destination-repository-drift-2026-09-17.txt).

The real destination acceptance record is now represented by the
[`destination-owner-acceptance-template.txt`](../acceptance/destination-owner-acceptance-template.txt)
schema. `scripts/validate-destination-owner-acceptance.sh` accepts only a
complete `REAL_DESTINATION` record with every owner-visible workflow marked
`PASS`, rejects the untouched template, and rejects secret-like fields. This
does not manufacture owner acceptance; it makes the missing session explicit
and provides a fail-closed artifact for the eventual cutover.

The final read-only gate is
[`scripts/check-production-cutover-authorization.sh`](../scripts/check-production-cutover-authorization.sh).
It requires the validated real-destination record, an explicit
`HADES_CUTOVER_AUTHORIZED=1` operator decision, and a passing infrastructure
preflight before any later cutover action can begin. The gate itself performs
no routing, service, or cleanup mutation.

After the authorized change window, run
[`scripts/verify-production-cutover-complete.sh`](../scripts/verify-production-cutover-complete.sh)
with the same protected rollback inputs. It verifies the real acceptance
record, expected `hades-core` SSH identity, normal `hades.local` health, independent rollback custody, absence of
the six laptop production containers and Hermes runtime, and preservation of
the two development checkouts. It also requires a secret-free
`laptop-production-decommission/v1` evidence record covering service disablement,
allowlisted cleanup, ambiguous-material preservation, and before/after disk
usage. It is read-only and intentionally fails while the laptop remains the
production host.

The cleanup record is validated independently by
[`scripts/validate-laptop-decommission-record.sh`](../scripts/validate-laptop-decommission-record.sh),
which rejects incomplete, unknown, duplicate, or secret-bearing fields.
The operator starting point is
[`acceptance/laptop-production-decommission-template.txt`](../acceptance/laptop-production-decommission-template.txt);
it is deliberately not a passing record.

The final verifier accepts the protected, checksum-verified LLDAP and Agent
Zero rollback archives as sufficient for laptop-independent rollback while
reporting their separate long-term encryption-custody gate; it does not claim
that owner-managed encrypted recovery has been completed.

## Deferred laptop cleanup allowlist

No source cleanup is authorized until owner acceptance and `hades.local`
cutover pass. The exact production runtime set identified for a later,
reversible cleanup is:

```text
service:    user-level systemd hades-hermes.service
containers: hades-open-webui, hades-hindsight, hades-grocy,
            hades-agent-zero, hades-searxng, hades-lldap-production
state:      the six migrated data stores and the production Hermes profile
            listed in the source package manifest
```

The laptop HADES and `hades-infra` checkouts, SSH/Tailscale/admin tooling,
staging containers and volumes, development assets, personal files, and
ambiguous model/cache material are explicitly excluded until individually
classified. Cleanup must record before/after disk usage and preserve the
Alexandra rollback package.

The pre-cutover laptop baseline captured on 2026-09-16 was `/home` at
`237G/280G` used with `40G` available; all six production containers were
running. The large Open WebUI data tree exceeded the bounded per-directory
measurement window, so no component-level size is claimed from that partial
walk.

A later read-only Docker inventory confirmed the same six production
containers and recorded aggregate host accounting of `178.3G` across 640
images (`127.4G` currently reclaimable) and `3.016G` across 387 local volumes
(`2.86G` currently reclaimable). Those Docker totals include staging and other
workloads, so they are not a production-cleanup size claim. The individual
volume mountpoints are permission-restricted to their owning services; no
size was guessed from an unprivileged walk. Post-cutover cleanup must record
component-level before/after measurements after each explicitly classified
artifact is stopped or removed.

The read-only inventory helper
[`scripts/inventory-laptop-decommission.sh`](../scripts/inventory-laptop-decommission.sh)
captures the current disk baseline, Hermes user-service state, the six named
production containers, Docker accounting, and the preserve/review/candidate
classification without stopping or deleting anything. Invoke it as
`.../inventory-laptop-decommission.sh before` and again as
`.../inventory-laptop-decommission.sh after` so the disk evidence is
unambiguous. It is preparation for a post-acceptance operator cleanup, not a
cleanup command.

Tartarus and Hypnos GPU qualification is parallel infrastructure work and is
not a prerequisite for this application migration.
