# Open WebUI 0.11.1 to 0.11.4 migration and rollback — 2026-10-09

## Artifacts

- Legacy HADES Open WebUI image: `hades-open-webui@sha256:75df14805e0e95157166b9672678e2285ce2ae58126c71232d68d6a95a30b629`.
  Its upstream image labels identify Open WebUI 0.11.1 at source revision
  `d3e8bf3405e848cfba377814d0aa7ba7290e414d`, matching the tracked 0.11.1
  upstream base digest.
- New HADES staging image: `hades-open-webui@sha256:86b448b4ae005c7971f96930f8a52677ed788d8f726dfe679367cd2046e4650e`,
  built from official Open WebUI 0.11.4 base digest
  `sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f`
  with the tracked HADES adapters.
- Replay: [`test-open-webui-migration-rollback-candidate.py`](../scripts/test-open-webui-migration-rollback-candidate.py).

## Results

The disposable 0.11.1 instance created synthetic Alpha (admin) and Beta
(user) accounts, configured a local synthetic model, and persisted an Alpha
chat marker. Beta received HTTP 401/403 when requesting Alpha's private chat.
After the old container stopped, the test cloned its data directory into an
upgrade copy and an untouched rollback snapshot.

The patched 0.11.4 candidate opened the upgrade copy, accepted both existing
passwords, preserved their identities and Alpha's private chat, kept Beta's
cross-user request denied, and passed SQLite `integrity_check`. Those checks
also passed after restarting the candidate container. The untouched
pre-upgrade snapshot then started again under the 0.11.1 image, with both
accounts and Alpha's private chat intact and Beta still denied.

All three arms used synthetic users, messages, a local mock model, and
temporary data directories. They did not read, change, or copy production
WebUI data. The test exercises rollback by restoring a pre-upgrade snapshot;
it does not attempt to downgrade the already-migrated 0.11.4 database in
place.

This closes the disposable database migration/backup-restore gate for the
recorded candidate pair. It does not prove production database safety, LDAP
group/user migration, Channels or shared-folder migration, document retrieval,
external build provenance, or direct owner acceptance. Production remains
pinned to 0.11.1 pending those other gates.
