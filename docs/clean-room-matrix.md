# Clean-room evidence matrix

This matrix separates tested evidence from advertised configuration. A green
synthetic contract is not a full owner deployment.

| Target | Install | Restart/re-entry | Full owner acceptance | Status |
|---|---|---|---|---|
| Fedora Server 44 x86_64 | generated private records and pinned containers on two fresh guests | tracked subset and generated synthetic stack rebooted | full private owner records not copied | `SYNTHETIC VERIFIED` |
| Rocky Linux 10.2 x86_64 | actual pinned application composition and generated installer | generated runtime reboot and isolation checks | owner-specific state not copied | `SYNTHETIC VERIFIED` |
| Ubuntu LTS | not run | not run | not run | `UNVERIFIED` |
| Debian stable | not run | not run | not run | `UNVERIFIED` |
| Arch | not run | not run | not run | `UNVERIFIED` |
| openSUSE | not run | not run | not run | `UNVERIFIED` |
| aarch64 | source/contracts only | not run | not run | `UNVERIFIED` |

The installer rejects unsupported OS versions rather than silently claiming
portability. Any manual clean-room repair is red until encoded and rerun from a
reset machine.

`scripts/test-host-os-detection-matrix.sh` additionally exercises the
non-mutating host-preparation classifier in disposable Fedora 44, Rocky 9,
Ubuntu 24.04, Debian stable, Arch, and openSUSE containers. Fedora/Rocky are
accepted as supported plan-only targets; the other four fail closed. This is
OS-classification evidence only and does not upgrade the unverified rows into
full install, restart, or owner-acceptance evidence.
