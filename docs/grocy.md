# Grocy integration

The Grocy adapter treats the configured service as canonical household
inventory. It reads through the authenticated API, validates bounded writes,
requests confirmation for consequential changes, and reads state back after a
write. Private endpoint URLs, credentials, and real household data are
operator-managed configuration and do not belong in public HADES source.

Synthetic tests cover owner/household capability separation, shared stock and
shopping-list workflows, recipe feasibility, idempotency, outages, correction,
and concurrent writes. Real household acceptance remains owner-gated.
