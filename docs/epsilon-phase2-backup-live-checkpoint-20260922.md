# Backup verification checkpoint

Deployment-specific backup freshness, destination, artifact paths, and custody
are private operational evidence in `hades-infra`. The detailed historical
checkpoint is retained in the private archive at
`docs/private-public-hades-source-archive-20261001/`.

The public Epsilon contract reports only the configured source's verification
state and timestamps. It does not claim that all host or VM data is covered,
that a local copy is off-site, or that a restore has succeeded.
