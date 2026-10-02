# Bounded self-service workload contract

The public workload contract uses a fixed synthetic catalog, explicit owner
confirmation, stable resource IDs, quotas, sharing, revocation, and canonical
read-back. A constrained executor may act only on a previously approved,
validated target. Household users cannot create infrastructure or grant
privilege.

The public test suite uses disposable fixtures and performs no production
lifecycle action. Actual templates, target placement, host IDs, service
readiness, addresses, and exposure policy are deployment-private and require
separate owner authorization.
