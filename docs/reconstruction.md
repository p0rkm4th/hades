# HADES reconstruction contract

A supported installation is rebuilt from the public repository, explicit
protected private inputs, documented prerequisites, and canonical backups. It
must not depend on copied development directories, container volumes, shell
history, or untracked configuration.

## Canonical flow

1. Clone the public repository on a clean supported host.
2. Run preflight and host preparation.
3. Generate or provide explicit private inputs with documented ownership and
   permissions.
4. Run the idempotent installer.
5. Run the non-mutating doctor and functional validation.
6. Re-run installation to prove state preservation.
7. Reboot and validate automatic recovery.
8. Exercise backup, destroy, clean install, restore, and functional read-back
   on disposable infrastructure.

## Contract boundaries

- Public fixtures use synthetic identities and reserved example addresses.
- Production endpoints, topology, credentials, and owner custody remain in
  private configuration.
- Optional integrations stay disabled when their private inputs are absent.
- A clean application container is not a clean-host proof; systemd, filesystem
  ownership, container runtime, security labeling, network exposure, and
  reboot behavior must be exercised on a supported guest.

Current independent-host evidence and operator procedure are maintained in
private `hades-infra`; public CI is not an installer simulator.

## Public evidence summary

| Evidence level | Status | Meaning |
|---|---|---|
| Full-stack synthetic clean reconstruction | PARTIAL | Synthetic installer/recovery coverage exists; independent supported-host proof is tracked privately. |
| Actual-image application composition | PASS | Pinned application images have a disposable composition contract. |
| Full application clean reconstruction | PARTIAL | Complete independent clean-host proof is not represented by public synthetic checks. |
| Fresh-install synthetic household soak | PASS | Generic synthetic identities exercise representative household workflows. |
| Fresh-install full application household soak | PARTIAL | Owner deployment acceptance remains a separate gate. |

The actual-image composition harness is `test-full-application-image-startup.sh`.
Deployment-specific guest IDs, paths, and runtime logs remain in private
`hades-infra`.
