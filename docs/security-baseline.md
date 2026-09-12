# Security Baseline

- Keep this repository free of credentials. Use ignored environment files or
  narrowly scoped secret stores outside Git.
- Separate normal `hades` operation from any future `hades-admin` authority.
- Start read-heavy and private-by-default: Finance, NetBox, and Proxmox
  read-only; Home Assistant selected entities only; SSH restricted to a
  dedicated account; no unnecessary Docker socket access.
- Do not use privileged containers, host-root mounts, public administrative
  exposure, or unrestricted shared credentials.
- Prefer private/Tailscale networking and verify every interface actually
  exposed.
- Treat owner authentication, Plaid authorization, and any destructive action
  as explicit gates.
- Preserve owner data when provenance is ambiguous; do not run broad cleanup,
  prune, migration, or replay operations without a bounded target.

