# HADES clean-host contract

The supported reconstruction target is one fresh Fedora Server 44 or Rocky
Linux 9/10 guest, x86_64 or aarch64, with systemd. An x86_64 target must expose
x86-64-v2 CPU features because the pinned Open WebUI image includes NumPy built
for that baseline; virtual guests must use a host-passthrough CPU model.
Minimum: 2 dedicated CPU cores, 8 GB RAM, and 40 GB free disk before the
first image acquisition. After all pinned component images are present, a
rerun requires 8 GB free working reserve. Recommended:
4 cores, 16 GB RAM, and 100 GB free
disk. The host must have working DNS and private-network access to explicitly
configured upstreams. A container runtime with the Docker Compose plugin,
`curl`, `git`, and `openssl` is required. Hermes 0.21.2 is built from its
verified source archive with Python 3.13 and the manifest-pinned uv version;
the host helper installs those tools under `/opt/hades-hermes-tools` so the
Hermes build does not depend on whichever Python or uv happens to be on `PATH`.
GPU and local Ollama are optional: inference may run on a separate
private host through the documented Hermes model endpoint.

On a minimal Fedora guest, the bounded host prerequisite step installs
`moby-engine`, `docker-compose`, and Python 3.13, along with `git` and
`openssl`. On Rocky 9/10, the helper enables CRB, installs
EPEL and Python 3.13, adds Docker's official CentOS-compatible RPM repository,
and installs `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`,
and `docker-compose-plugin`. Both paths install the manifest-pinned uv into
`/opt/hades-hermes-tools/uv-<version>` and enable Docker. The HADES installer validates these prerequisites
but does not install packages before its non-mutating preflight; this keeps an
unsupported or incomplete host from being partially modified. The same step
is available as the plan-first `scripts/prepare-hades-host.sh`; use `--apply`
only on the intended supported guest.

Install the pinned Hermes source before installing the stack:

```sh
sudo scripts/prepare-hades-host.sh
sudo scripts/prepare-hades-host.sh --apply
sudo scripts/install-hermes-artifact.sh --prefix /opt/hades-hermes
sudo scripts/install-hades.sh --inputs /etc/hades/operator-inputs.env
```

The core HADES guest is distinct from a local model-inference host. RTX/GPU
drivers, model caches, and Ollama state are not reconstruction dependencies.
All user-facing defaults bind only to approved/private interfaces; component
exposure is recorded in the component manifest.

The clean layout is:

| Path | Provenance and purpose |
|---|---|
| `/opt/hades` | source-controlled checkout and reconstructable assets |
| `/etc/hades` | generated configuration from tracked templates |
| `/etc/hades/secrets` | explicit operator inputs/generated secrets, narrow permissions |
| `/var/lib/hades` | restored canonical persistent state or new component state |
| `/var/backups/hades` | private backup staging; not source |
| runtime scratch | upstream/container-managed temporary data |

The seasoned deployment may use different private paths; that is an operator
record mapping, not a reason to copy untracked machine state into this tree.

The installer fails before mutation on an unsupported OS version, missing required tools,
bad inputs, unsafe secret permissions, invalid URLs, port collisions, or missing
tracked source. It does not install a GPU stack, migrate production, or delete
state.

The tracked LLDAP Compose contract runs as UID 1000. Its three file-backed
identity secrets therefore remain mode `0600` and are owned by UID 1000; this
is narrow service access, not a world-readable relaxation. The Compose
contract mounts them read-only with an SELinux `Z` relabel so a fresh enforcing
Fedora/Rocky host does not require a manual `chcon` or an SELinux-wide bypass.
