# Uninstall

`sudo scripts/hades uninstall --inputs /etc/hades/operator-inputs.env --confirm`
stops known runtime services and preserves source, state, secrets, and backups.
Permanent deletion is intentionally separate and owner-controlled. HADES never
silently deletes canonical household data or downloaded models.
