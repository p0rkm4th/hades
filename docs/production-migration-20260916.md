# Production migration contract

This public document records the safe migration sequence without deployment
identities or endpoint details. The detailed historical plan and acceptance
record are retained in private `hades-infra`.

1. Capture and verify a canonical production backup.
2. Provision a clean supported target using the canonical installer.
3. Restore through documented mechanisms and preserve stable identities.
4. Validate services, household isolation, memory ownership, and recovery.
5. Obtain owner acceptance on the clean target.
6. Prepare DNS or access-path cutover with an explicit rollback window.
7. Keep the old deployment available through the confidence period.
8. Retire the old deployment only after separate owner authorization.

This repository does not authorize production changes or cutover. Real
encrypted off-host custody remains owner-managed and is not implied by local
backup copies.
