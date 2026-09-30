# Hindsight worker identity: staged recovery plan

## Current finding

The production worker has run without `HINDSIGHT_API_WORKER_ID`, so the
container chose an identity derived from its runtime hostname. The tracked
Compose template assigns the stable identity `hades-hindsight`. Synthetic
tests against the pinned image show that a worker reclaims processing rows
only when their stored worker identity matches its own. Recreating a worker
with a different default identity leaves the old worker's rows untouched.

This establishes a configuration defect and a possible explanation for
stranded work. It does **not** identify the owner or cause of any production
row, and assigning the stable identity is not a repair for old rows owned by
unknown identities. Do not retry, replay, cancel, or delete production
operations or consolidations as part of this procedure.

## Before a production change

Treat this as a staged operator procedure. It does not authorize a production
change. First establish all of the following in a separately approved
maintenance window:

1. Confirm the exact Hindsight container, immutable image digest, Compose
   record, state mount, and current health from the live host. Do not infer
   those values from a sample or this repository.
2. Create a private, access-restricted native PostgreSQL export using
   [`scripts/backup-hindsight-native.sh`](../scripts/backup-hindsight-native.sh).
   Verify its checksum and `pg_restore --list` result. Keep the artifact outside
   Git and preserve the current database and image until post-change checks
   pass.
3. Save an access-restricted copy and checksum of the exact generated Compose
   record. Record the current worker identity if present, image digest,
   container ID, mount identity, `/health` and `/version` results, and
   aggregate-only operation/consolidation counts. Do not record credentials or
   query individual production operation rows.
4. Render and validate the proposed Compose configuration. Confirm that the
   only intended runtime change is the stable worker ID. Confirm that the
   immutable image, database mount, ports, network, model endpoint, and other
   environment settings remain identical.
5. Verify the native restore path and the exact rollback Compose record before
   scheduling the change. A checksum-valid export is necessary but does not by
   itself prove a complete restore rehearsal.

If any item cannot be verified, leave the production service unchanged.

## Bounded change and acceptance

After the preconditions and change authority are satisfied, recreate only the
Hindsight Compose service with the stable worker ID. Do not pull or promote an
image, change the data mount, modify Hermes, or restart unrelated services.
The installer/Compose path must preserve the existing persistent database.

Validate, without reading individual async-operation details:

- the Hindsight container is running the previously pinned image digest;
- the running `HINDSIGHT_API_WORKER_ID` equals the rendered Compose value;
- `/health` and `/version` are healthy and unchanged as expected;
- the database mount and container port exposure are unchanged;
- aggregate backlog counts have not unexpectedly increased; and
- an already-authorized, harmless memory recall succeeds without a new
  production retain or replay.

Keep the old export and Compose record through the confidence window. A future
restart will then reuse the same worker identity and may reclaim rows owned by
that stable identity. Rows associated with the previous ephemeral identity
remain unclassified and untouched; diagnose them separately before any
recovery action.

## Rollback

If the recreated service fails health, version, mount, or bounded recall
validation:

1. Stop the change and do not retry, replay, or delete async work.
2. Restore the exact saved Compose record and its previous environment values.
3. Recreate only the Hindsight service with its original immutable image and
   original persistent database mount.
4. Verify service health and database connectivity. Preserve both the failed
   change evidence and the known-good export for later diagnosis.

Rollback restores the previous runtime configuration; it does not recover
unknown-owner processing rows or resolve the consolidation backlog. A database
restore is a separate recovery action with its own reviewed target, identity
mapping, and acceptance plan.

## Evidence boundary

The source Compose contract, doctor and install-validator checks, and pinned-
image synthetic worker recovery tests pass. When a Hindsight Compose path is
present, `hades-doctor` and `validate-install.sh` check the rendered identity
against the running container for both legacy v1 and generated v2 operator
inputs; without a Compose path they report that the identity could not be
checked. Production currently lacks the stable worker ID. No
production Compose change, restart, memory write, operation inspection,
retry, replay, deletion, or database restore has been performed for this
finding. Update this document only when new evidence changes those statements.

For an aggregate-only production snapshot, run
`python3 scripts/hindsight-aggregate-stats.py` on HADES Core. It accepts only a
literal loopback HTTP address, reads the bank list and each bank's `/stats`
endpoint, and prints the bank count plus the four aggregate backlog totals.
It never prints or persists bank identifiers, names, or row data, and it does
not call operation, memory, retry, replay, or mutation endpoints. A failed or
malformed bank response fails the whole snapshot rather than reporting partial
totals.

### Disposable native backup/destroy/restore rehearsal — 2026-09-27

`scripts/test-hindsight-native-backup-restore.sh` now exercises the tracked
native backup helper against the manifest-pinned Hindsight image. It creates a
synthetic bank and explicit-memory fact through Hindsight's API plus a marker
table in a disposable source volume, writes and validates a custom-format
PostgreSQL archive and checksum, destroys the source container and volume,
restores the archive into a fresh volume with the pinned image's `pg_restore`,
and verifies the marker, canonical tagged-memory listing, fresh recall result,
and Hindsight health. The extraction model is a local synthetic stub. The
harness passed and removes both volumes, both containers, the archive, and the
synthetic credential file on exit.

This proves a bounded native archive can restore into a fresh instance of the
same pinned image and preserve one synthetic Hindsight memory through its list
and recall APIs. It does not validate production data, stable subject-to-bank
mapping, production memory recall, old worker-owned queue rows, off-host
custody, or the production rollback package. The production worker identity
remains absent; its maintenance gate is unchanged.

### Aggregate-only production snapshot — 2026-09-28 02:13 UTC

Strict-host-key read-only SSH confirmed the pinned Hindsight container is
running with both published listeners bound to `127.0.0.1`; the stable
`HINDSIGHT_API_WORKER_ID` remains absent. The new aggregate helper completed
all 13 bank `/stats` reads and reported 3 pending / 470 failed operations and
54 pending / 1,118 failed consolidations, unchanged from the prior snapshot.
No identifiers, names, memory rows, or operation rows were emitted or
retained. No retry, replay, delete, restart, config change, or memory action
occurred. The stable worker identity and safe ownership of existing work
remain unresolved; this observation does not authorize changing production.

### Aggregate-only refresh and disposable worker recreation — 2026-09-28 14:48 UTC

Using the local aggregate helper over a temporary strict-host-key SSH tunnel,
all 13 production bank `/stats` requests succeeded. Counts are 3 pending / 470
failed operations and 57 pending / 1,118 failed consolidations. The Hindsight
health endpoint reports healthy with database connected. The pending
consolidation count has risen by three from the last recorded 54; no bank
identity, memory row, or operation row was retained. No retry, replay, delete,
restart, configuration change, or memory action occurred.

`scripts/test-hindsight-ephemeral-worker-recreation.sh` passes against the
manifest-pinned image: recreating a container without an explicit worker ID
changes its hostname-derived identity and leaves a synthetic processing row
owned by the old ID untouched; restoring that ID returns only that synthetic
row to pending. This confirms the previously documented mechanism in the
current local image. It does not identify any production row owner or make
production recovery safe. No production service or state changed.


### Aggregate-only production refresh — 2026-09-29

Strict-host-key SSH to the documented VM 802 account ran
`scripts/hindsight-aggregate-stats.py` through stdin, without copying the helper
to the guest. All 13 bank `/stats` requests succeeded: 3 pending / 470 failed
operations and 57 pending / 1,118 failed consolidations. No bank identifiers or
operation rows were emitted or retained.

The pinned container remains running with zero restarts on image
`sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`;
`/health` reports healthy/database connected, `/version` reports API 0.9.2, and
the published listener remains loopback-only at `127.0.0.1:8888`.
`HINDSIGHT_API_WORKER_ID` is still absent. The counts match the 2026-09-28
snapshot; this does not establish ownership or cause of failed/pending rows.
No memory rows, operation details, retries, replays, deletes, restarts, or
configuration changes occurred. Production remains unchanged, and worker
identity recovery remains gated on the documented maintenance approval, native
backup, and rollback prerequisites.
