# Backup and restore

Run `scripts/hades backup --path /protected/backup-staging` for the supported
SQLite checkpoint. Run `scripts/hades restore --path CHECKPOINT` to verify
integrity without changing application state; each authoritative component
then uses its documented native restore procedure. See
[`docs/backup-restore.md`](docs/backup-restore.md).
