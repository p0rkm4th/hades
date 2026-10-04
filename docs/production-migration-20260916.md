# HADES deployment migration guide

This guide describes a generic migration path. Deployment names, addresses,
account names, machine identifiers, credentials, and rollback locations belong
in the operator's private infrastructure repository and are supplied at run
time. This repository does not identify a household's current host or client
network.

## Before migration

- Confirm the target OS and hardware meet the supported-host contract.
- Record the source revision, deployed component versions, and persistent
  volumes in the private operator record.
- Create and validate canonical backups for identity, conversations, memory,
  household data, and service-specific state. A copied volume is not a restore
  rehearsal.
- Generate the private-input bundle from the tracked templates. Do not commit
  passwords, tokens, private endpoint maps, or deployment records.
- Keep the existing deployment available as rollback until the new target has
  passed owner and household acceptance.

## Rebuild and validate

1. Provision a clean supported guest using the operator's hypervisor procedure.
2. Clone the HADES repository and follow its canonical installation guide.
3. Run preflight, host preparation, installation, doctor, and functional
   validation in the documented order.
4. Restore only from canonical backups and validate stable identity mappings,
   private-memory isolation, shared household state, and service recovery.
5. Reboot the guest and repeat the reduced functional checks without manually
   starting services outside the documented contract.
6. Complete owner acceptance and household-boundary checks before routing any
   clients to the target.

## Cutover and recovery

Client DNS, DHCP, firewall, or tunnel changes are owned by the operator's
network authority and are not performed by the application installer. Change
those records only after explicit owner approval and a documented rollback
path. Retain the source runtime through the confidence window. Decommission it
only after the owner accepts the target and its backups and restore procedure
have been verified.

For a HADES-only upgrade on an existing host, use
[`upgrade-decommission.md`](upgrade-decommission.md) and the documented
component-specific backup and rollback steps. Private deployment parameters
are not included here.
