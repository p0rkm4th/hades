# Phase 3 bounded production canary runbook

This runbook applies only to the standing-authorized, HADES-local,
read-only Phase 3 templates:

- Server Health Watch
- Low Inventory Summary
- Weekly Household Summary
- Backup Verification

It does not authorize arbitrary n8n workflows, source writes, external
notifications, broader grants, or production migration. Keep schedules inactive
until the complete fixed-source/result path and rollback have passed.

## Preflight and rollback snapshot

1. Confirm the HADES commit, generated deployment provenance, active service
   units, immutable container image digests, compose paths, bind-mounted WebUI
   assets, and current Epsilon package manifest. Do not print environment values
   or credential contents. If the deployment is assembled from multiple source
   revisions or has local artifacts, record each checkout revision and each
   packaged artifact digest separately. Do not assign one guessed HADES SHA to
   a mixed component tree. A noncanonical active artifact must be reconciled
   to reviewed source before provenance is refreshed or the canary changes
   production.
2. Create a protected, timestamped rollback directory. Export existing n8n
   credentials with `n8n export:credentials --all` **without** `--decrypted`,
   and export workflows with `n8n export:workflow --all`. Protect both exports
   as mode `0600`; retain the existing n8n encryption key and data volume.
3. Back up the current Epsilon source package/provenance, Hermes overlay and
   systemd drop-ins, WebUI compose file and bind-mounted assets. Record current
   image IDs so rollback can restore the exact prior image. Back up persistent
   application data through its documented backup path before replacing an
   image. Do not overwrite or delete existing backups.
4. Record all new paths and exact rollback actions before changing them. Keep
   the runner state database after rollback; it is audit/recovery evidence.

## Install and validate while inactive

1. Package the repository's Epsilon endpoint and complete
   `integrations/automation` package into the existing generated root with
   `scripts/package-epsilon-source.py`. Verify the emitted manifest and file
   hashes. Preserve the existing backup/provenance inputs.
2. Create one dedicated `hades-phase3` system group for the Epsilon and Hermes
   service processes. Provision the new isolated state directory as
   `root:hades-phase3` mode `2770`. Set the same
   `HADES_EPSILON_PHASE3_STATE_FILE` and
   `HADES_EPSILON_PHASE3_STATE_GROUP=hades-phase3` in both services. Use
   `SupplementaryGroups=hades-phase3`, `UMask=0007`, and narrow
   `ReadWritePaths` drop-ins on both units. Do not add either service account
   to the other's general groups. `Phase3Store` must create a `0660` database
   there; it refuses to widen an existing private database. Migrate legacy
   Phase 3 metadata into this new path and verify both service UIDs can read
   and write it before continuing. Run the repository cross-UID acceptance
   with a locally built immutable HADES Open WebUI image ID:

   ```sh
   HADES_PHASE3_SHARED_STATE_TEST_IMAGE="$(docker image inspect --format '{{.Id}}' hades-open-webui:0.11.1-hades-reconstructed)" \
     bash scripts/test-phase3-shared-state-contract.sh
   ```
3. Create distinct mode-`0600` runner and result-query keys with the tracked
   helpers. Keep separate Epsilon and Hermes result-key copies; never reuse the
   n8n runner key for result reads. Add one Epsilon systemd drop-in for the
   live LLDAP authority inputs, keys, and narrow writable state path. Do not
   add a guessed health URL. Restart Epsilon and verify the
   existing backup, inventory, and provenance endpoints still work, then
   validate signed dispatch, replay, revocation, private-file modes, and state
   persistence.
4. Import the named n8n Crypto credential from the protected runner key and
   import the tracked fixed dispatcher. n8n workflow import defaults to
   inactive; keep it inactive during validation. The graph may call only the
   signed HADES due/run routes and contains no user-selected URL or workflow.
5. Add only the Hermes result-query URL and its separate key-file path through
   a systemd drop-in. Set `HADES_INTEGRATIONS_ROOT` to the generated deployment
   root as well. Hermes may run from an older working checkout; the overlay
   inserts the generated package first, while `integrations.__path__` keeps
   legacy adapter packages discoverable. Verify that `Phase3Store` resolves
   from the packaged generated root and supports the configured shared group
   before restarting Hermes. Build the HADES Open WebUI image with the current
   pinned runtime as its base. Update the bind-mounted `hades-theme.js` asset
   and the private compose image reference as one rollback unit; the host bind
   mount takes precedence over the copy inside the image.
6. Restart one service at a time. Verify authentication, current LLDAP grants,
   one fixed-source result, requester/owner visibility, household sharing and
   revocation, notification isolation, restart persistence, and no external
   delivery. Do not use real Grocy writes or Hindsight mutations for acceptance.
7. Enable only an explicitly authorized fixed automation after manual
   end-to-end validation. Keep Server Health Watch and any Weekly Summary
   including health disabled until `HADES_EPSILON_HEALTH_URL` is configured to
   a validated canonical HADES health endpoint. Use the minimum allowed
   interval and HADES-local results only.

## Rollback

1. Deactivate the exact Phase 3 dispatcher workflow first. Verify it is
   inactive and no further due poll/run is being dispatched.
2. Restore the prior WebUI compose image reference and bind-mounted asset from
   the protected snapshot; restart Open WebUI and verify the old image digest.
3. Remove only the Phase 3 Hermes drop-in and restore its prior overlay if it
   was changed; restart Hermes and verify the previous health/provenance.
4. Remove only the Phase 3 Epsilon drop-in and restore the prior packaged
   Epsilon source files from the snapshot; daemon-reload, restart Epsilon, and
   verify the prior backup, inventory, and provenance endpoints.
5. Delete the exact imported Phase 3 workflow and credential after confirming
   the workflow is inactive. Remove only newly created key files after the
   credential is removed. Keep the isolated Phase 3 state database and its
   protected snapshot for diagnosis; do not delete or reseed it automatically.
6. Re-run the non-mutating service checks and confirm the previous immutable
   images, service states, listener exposure, and data volumes are restored.

Any failed or `UNKNOWN` run stops further automatic execution until an operator
reviews the stored outcome. A rollback never replays an uncertain source read.
