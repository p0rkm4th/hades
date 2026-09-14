# HADES clean-host contract

The supported reconstruction target is one fresh Fedora Server or Rocky Linux
guest, x86_64 or aarch64, with systemd. Minimum: 2 dedicated CPU cores, 8 GB
RAM, and 40 GB free disk. Recommended: 4 cores, 16 GB RAM, and 100 GB free
disk. The host must have working DNS and private-network access to explicitly
configured upstreams. A container runtime with the Docker Compose plugin,
`curl`, `git`, and `openssl` is required; Python is needed only for repository
validators. GPU and local Ollama are optional: inference may run on a separate
private host through the documented Hermes model endpoint.

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

The installer fails before mutation on unsupported OS, missing required tools,
bad inputs, unsafe secret permissions, invalid URLs, port collisions, or missing
tracked source. It does not install a GPU stack, migrate production, or delete
state.

The tracked LLDAP Compose contract runs as UID 1000. Its three file-backed
identity secrets therefore remain mode `0600` and are owned by UID 1000; this
is narrow service access, not a world-readable relaxation.
