# Backup and restore

Run `scripts/hades backup --path /protected/backup-staging` for the supported
SQLite checkpoint. Run `scripts/hades restore --path CHECKPOINT` to verify
integrity without changing application state. For an already-prepared and
stopped staging target, `scripts/hades restore --path CHECKPOINT --target TARGET
--apply --confirm` applies the Open WebUI, LLDAP, Grocy, and Hermes SQLite
files and retains a rollback checkpoint. Hindsight/PostgreSQL, Agent Zero,
SearXNG, secrets, and external canonical applications still use their native
procedures. See
[`docs/backup-restore.md`](docs/backup-restore.md).
