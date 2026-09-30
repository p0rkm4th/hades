# Epsilon Phase 2 Backup Verification — Live Checkpoint

## Live evidence

- Fixed private source endpoint: HADES Core loopback-to-Docker bridge only,
  `<PRIVATE_LAN_ADDRESS>:8643`; no public listener.
- Approved targets: HADES repository bundle and infrastructure repository
  bundle.
- Both protected artifacts were copied from Alexandra's temporary landing zone
  into a HADES verification cache. This cache is not an independent disaster
  recovery domain.
- SHA-256 matched for both artifacts.
- `git bundle verify` passed in a fixed bare verification context.
- n8n run-now execution projected `HEALTHY` and the bounded reason
  `checksum matched and git bundle verified`.
- Safe fixture projections passed: `MISSING`, checksum `FAILED`, invalid
  content `FAILED`, `STALE`, and restored `HEALTHY`.
- Stopping the source endpoint projected `SOURCE_UNAVAILABLE` through n8n.
- Repeated state transitions remain deduplicated by the typed state service.

## Current classification

```text
BACKUP VERIFICATION
    BACKEND READY
    DOM ACCEPTANCE BLOCKED
```

The authenticated runtime route can create, confirm, list, and run the owner
Backup Check. The reusable Playwright matrix still has a settling defect on the
Backup prompt in the real Open WebUI session; therefore this lane is not
DOGFOOD GREEN and Low Inventory has not been promoted.

The isolated DOM reproducer additionally shows the sign-in session is not
reaching `#chat-input` consistently after authentication, despite the same
credentials succeeding against the authenticated API. This is the current
acceptance-harness blocker, not an authorization reason to promote the next
template.
