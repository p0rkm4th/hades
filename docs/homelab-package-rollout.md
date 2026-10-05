# Homelab adapter package rollout

This procedure updates only the external `homelab-readonly` MCP package and
its selected Hermes profile argument. It does not update Hermes, the
`sitecustomize.py` overlay, other MCP registrations, the systemd unit, or
`hermes.env`. The offline composer is
[`scripts/compose-homelab-package.py`](../scripts/compose-homelab-package.py).
It packages tracked Python files from a clean HADES commit and emits a
deterministic manifest. It does not transfer, install, or activate anything.

## Preconditions

- Use a clean HADES checkout at the exact full commit SHA under review. Record
  the HADES and `hades-infra` revisions in the protected deployment record.
- Resolve the active Hermes unit, running profile, package argument,
  `HERMES_HOME`, and service identity from the running service and protected
  deployment records. Do not infer them from a default profile or a remembered
  path.
- Confirm the current service is healthy. Capture the active profile hash,
  package file inventory/hashes, and any existing provenance record before
  changing the profile. If the current package fails exact provenance (as the
  known mixed bundle does), record that failure as the rollback baseline;
  do not represent it as a verified package identity. The provenance writer
  must use the same active unit, profile, source checkout, and package root
  that Hermes selects after activation.
- Have a tested owner and household acceptance route available. If acceptance
  cannot authenticate, stop before activation; do not reset credentials or
  weaken authentication to get a pass.
- Store backups and staging outside the source checkout. Use the host's
  protected deployment directories and least-privilege ownership from its
  deployment record. Do not place private paths, credentials, or topology in
  this public runbook.

## Compose and inspect

From the clean source checkout, choose a new immutable output directory and an
external manifest path in protected storage. Both parent directories must
exist and must not be group/world writable.

```bash
HADES_SHA=0123456789abcdef0123456789abcdef01234567
python3 scripts/compose-homelab-package.py \
  --source-repo /absolute/path/to/clean/hades \
  --revision "$HADES_SHA" \
  --output "/protected/packages/homelab-readonly-$HADES_SHA" \
  --manifest "/protected/manifests/homelab-readonly-$HADES_SHA.json"
```

Replace the example SHA with the reviewed commit and the example directories
with existing protected directories available to the operator. The example
SHA is a format placeholder and is not a HADES revision.

The command refuses dirty source trees, mismatched revisions, symlinks,
unsafe paths, and existing output. Review the manifest file list and hashes;
confirm they represent the exact tracked `integrations/homelab-readonly`
tree at the stated commit. Transfer the package and manifest over the approved
administrative channel. Recheck file hashes and required read permissions on
the target before proceeding. Keep the package immutable after composition.

## Back up and activate

1. Make a root-only, mode-`0700` rollback directory. Copy the selected profile,
   complete active package, and existing provenance record into it without
   following symlinks. Record the hash of each file and the owner, group, and
   mode of the profile, package files/directories, and provenance record.
   Preserve this backup until the rollout is accepted.
2. Prepare a temporary copy of the active profile in the same directory as
   the active profile. Change only the `homelab-readonly` server argument to
   the new immutable `server.py` path. Preserve all other profile bytes,
   registrations, owner, group, and mode. Validate the profile syntax and
   review a diff that contains only this argument change.
3. Immediately before replacement, re-read the active profile and require its
   hash to equal the precondition hash. If it changed at any point during
   preparation, stop and re-review; never overwrite an intervening update.
   Perform this within an exclusive deployment window in which no other
   operator or automation can update the profile until activation completes.
4. Atomically replace the active profile with the reviewed temporary file.
   Do not edit the active package in place. Do not run the full HADES installer
   or reload the systemd daemon.
5. Restart the already active Hermes unit once. If restart or health checks
   fail, follow the rollback steps immediately.

## Verify and record

- Run the deployed-provenance writer against the exact clean HADES and
  `hades-infra` revisions, active service, selected profile, and selected
  package root. Require its source revision and package source-tree identity
  to match the composer manifest. Verify the manifest's file list, each file
  SHA-256 and byte size against the installed package. The provenance
  `package_tree_sha256` and composer `package_sha256` use different inputs and
  are not expected to equal one another. The provenance writer also compares
  installed package files directly with Git blobs from the claimed clean
  source revision. Start from the documented
  invocation in [`docs/hermes-overlay-inventory.md`](hermes-overlay-inventory.md)
  and supply `--homelab-package-root` for the selected external package.
- Verify the Hermes service is active and the selected MCP starts from the new
  package. Make a fresh read-only homelab request and confirm its result is
  well formed and grounded in the configured sources.
- Run the approved fresh owner and household acceptance cases. Verify owner
  visibility and household redaction. A container health check alone is not
  acceptance.
- Record the old and new profile hashes, complete package hashes, source
  revisions, provenance result, restart time, and acceptance outcome in the
  protected deployment record. Retain the rollback copy until the owner
  acceptance decision.

## Roll back

Rollback only if the active profile still hashes to the exact candidate hash
applied by this rollout. If it does not, stop and inspect the newer change;
never overwrite it with a stale backup.

When the hash guard matches, atomically restore the saved profile with its
recorded owner, group, and mode; restore the saved provenance record and its
metadata, or record that provenance was rolled back if no prior record
existed. Restart the same Hermes unit once, then verify service health and the
restored selected package against the recorded baseline (which may itself be
unverified). Keep the failed candidate package and protected logs for
diagnosis. Do not delete the previous package or rollback copy as part of
activation.

## Limits

The composer and runbook do not authorize source ACL changes, host-account or
key changes, or Proxmox, NetBox, Kuma, or inference mutations. The provenance
writer verifies configured disk bytes, not code already imported into a
running process; restart plus a fresh functional request is required. `hades
doctor` checks general service/profile state but does not establish exact
external package parity. Independent off-host encrypted recovery remains
unconfigured and owner-managed.
