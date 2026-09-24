# Install HADES

See [`docs/installation.md`](docs/installation.md) for the complete contract.
The reference path is Fedora Server 44 or Rocky Linux 9/10 with systemd,
Docker Compose, x86_64/aarch64, 2+ cores, 8 GiB RAM, and 40 GiB free disk.
`scripts/hades setup --test-mode` is the non-mutating product-level first-run
plan. It checks the requested profile/exposure/owner/model choices without
creating files or accounts. A real setup requires root because it creates the
dedicated `hades-runtime` service account, generates fresh local secrets,
builds the pinned UI artifact, installs the pinned Hermes artifact, and then
invokes the bounded installer.

`scripts/hades preflight` is non-mutating. Use `--test-mode --root DIR` for a
credential-free rehearsal; it creates no containers, users, or provider calls.
