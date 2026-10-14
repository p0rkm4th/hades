# Open WebUI 0.12.0 production promotion

Status: **promoted; production health and bounded synthetic owner acceptance passed**.

## Active artifact

- Open WebUI: `0.12.0`
- Upstream source: `15818d88fd7bde1b73de33590f50d15d21e8d7c1`
- Upstream amd64 base: `ghcr.io/open-webui/open-webui@sha256:208e824dd445548da7bd655a5e24718bf88112a7f60a807b5adb09096f2fd10b`
- HADES build source commit: `afd0912853301e484e7582d3b622b928c0e47662`
- Loaded image ID: `sha256:1e0eb50b453b55c44240046c02775404236525cb3000fee2f6d3e7fbcca25f32`
- Deployed archive SHA-256: `cbad7a365dd08b65f4a7ce9cb86a18930ed7b808b945f48ff598a8189d494cb0`
- Required HADES security adapters: fail-closed JWT/session, authority revocation,
  LDAP empty-group handling, and socket-disconnect fail-closed.
- The Channels response compatibility patch is absent; native 0.12.0 behavior
  passed the qualified stream acceptance.

The artifact's immutable identity and inputs are mirrored in
[`config/versions.env`](../config/versions.env). The qualification build and
candidate UI/migration evidence are recorded in
[`open-webui-0.12.0-qualification.md`](open-webui-0.12.0-qualification.md).

## Cutover and acceptance

Before migration, the exact 0.11.4 image, SQLite snapshot, uploaded state,
configuration/assets, Valkey auth-state, and runtime configuration were backed
up under protected host-only storage. Checksums and archive readability were
verified; a disposable Valkey restore confirmed exact active revocation-marker
parity. Rollback restores the exact 0.11.4 image together with the pre-migration
application/auth state, then verifies service health and fresh authentication.

The pinned 0.12.0 image started healthy, `/health` returned success, and the
version endpoint reported 0.12.0. Production synthetic owner and household
logins passed; an invalid user was denied. The household identity received 401
when attempting to read an owner-private chat. Temporary owner UI chats passed
the bounded kitchen, recipe list/detail, homelab, finance, ordinary-chat, and
capability-boundary checks without raw JSON, automation leakage, or unauthorized
domain writes.

The exact production Hindsight path passed explicit synthetic memory save,
fresh-chat recall, explicit forget, and post-forget non-recall. Hindsight showed
one valid `world` fact after save and no valid matching fact after forget. All
temporary chats were deleted; the protected report contains hashes and
predicates rather than response text. Candidate qualification separately
covers populated migration and rollback, session/revocation, LDAP, chat
lifecycle, sharing, streaming, and document isolation on the pinned artifact.

## Conditions and rollback

The 0.11.4 image and pre-upgrade state remain preserved. MFA, Realtime voice,
and Tool Search are off. The owner-only memory canary remains unchanged; broad
automatic retention remains off. Promotion does not authorize new sharing,
voice, or tool-search features.

Public CI for the source promotion and post-promotion `main` CI are recorded in
the release checkpoint once complete. Direct Scotty Dogfood remains active.
