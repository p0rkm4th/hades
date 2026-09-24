# Install HADES

See [`docs/installation.md`](docs/installation.md) for the complete contract.
The reference path is Fedora Server 44 or Rocky Linux 9/10 with systemd,
Docker Compose, x86_64/aarch64, 2+ cores, 8 GiB RAM, and 40 GiB free disk.
`scripts/hades preflight` is non-mutating. Use `--test-mode --root DIR` for a
credential-free rehearsal; it creates no containers, users, or provider calls.
