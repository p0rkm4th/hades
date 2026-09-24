# Upgrading HADES

Change one bounded component at a time: backup, preflight, retain the prior
artifact, apply, run doctor/validate, restart, and keep rollback material until
acceptance passes. `scripts/hades upgrade` wraps the bounded helper; unpinned
`latest` and bulk updates are outside the contract.
