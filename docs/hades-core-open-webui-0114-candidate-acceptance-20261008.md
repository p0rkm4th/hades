# Open WebUI 0.11.4 candidate acceptance

Date: 2026-10-08

## Tested artifact

- Source checkout: HADES review branch at `148b66e1bb29a6d3f27a9524681b805c94bd1e98`
- Build input: `ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f`
- Local immutable image ID: `sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`
- Local repository digest: `hades-open-webui@sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`
- Upstream Open WebUI version label: `0.11.4`
- Upstream source revision label: `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`
- Upstream image labels: version `0.11.4`, source revision `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`

Built with `HADES_OPEN_WEBUI_BASE_IMAGE_OVERRIDE` set to the immutable input
above using `scripts/build-open-webui-artifact.sh`, then passed the resulting
image ID directly to `scripts/test-open-webui-candidate.sh`. The local image
does not embed a HADES source revision label; the build input checkout SHA is
recorded here for reproducibility. Production pins and services were not
changed.

## Results

All checks passed:

- Alpha private chat completion and response persistence.
- Beta denial when retrieving Alpha's private chat.
- Private chat persistence after Open WebUI restart.
- Authenticated synthetic Channels enablement and private-channel creation.
- New shared conversation begins without inherited message history.
- Beta membership, shared posting, and Alpha read-back.
- Shared message persistence after Open WebUI restart.
- Channel membership does not grant Beta admin configuration or standard
  channel creation.
- Anonymous Channels access is denied with HTTP 401.
- A Channels model mention reaches the synthetic OpenAI backend and its
  streamed response is persisted in the channel timeline.
- Synthetic owner browser login, HADES theme CSS/JS loading, visible upload
  input, successful synthetic text-file upload, a model reply sent through
  the chat composer, and file/chat reference persistence after page reload;
  zero browser page errors. A fixed-vector mock embedding endpoint served the
  disposable upload flow. This used
  [`dom-open-webui-candidate-smoke.js`](../scripts/dom-open-webui-candidate-smoke.js)
  with Playwright 1.63.0 and the disposable backend.

Candidate containers, volumes, and networks were absent after the acceptance
script completed.

The browser run surfaced an Open WebUI release-notes dialog on first login.
It intercepts the chat send control until dismissed; the visible dismiss
button worked. Keep this first-use step in the owner dogfood notes rather than
hiding the dialog with a HADES CSS override.

## Qualification boundary

This passes synthetic private-chat, Channels, and limited owner-authenticated
browser acceptance for the exact artifact built from the recorded review
checkout. It is not direct Scotty dogfood or production promotion. LDAP/group
provisioning behavior, document extraction and retrieval quality, shared
folders, broader responsive/theme review, full migration and rollback, and
reconstructed-deployment acceptance remain open. The locally built image has
an immutable ID but no embedded HADES-source provenance; record an external
build attestation or equivalent provenance for any promotion. Keep production
at 0.11.1 until the remaining gates pass.

## Repeat verification — 2026-10-09

The candidate acceptance command was rerun from the usability-reset checkout
against the same immutable local image ID and repository digest. Private-chat
isolation/persistence and Channels membership, shared-message persistence,
anonymous denial, and non-admin membership boundaries all passed again. The
private-chat suite also repeated the synthetic owner browser login, theme
asset, file-upload, chat persistence, and reload smoke. Containers and volumes
were removed by the harness. This repeat does not expand the qualification
boundary above: LDAP group synchronization, broader household browser use,
file extraction/retrieval quality, migration/rollback, external build
provenance, and direct owner preference remain open.

The unpatched image in the first repeat is not the current staging candidate.
Its LDAP group test found that removing a user's final directory group left a
stale Open WebUI membership. The current HADES staging image uses the
one-condition adapter and passed the full candidate suite plus LDAP
add/remove/revocation acceptance; see
[`hades-core-open-webui-0114-ldap-group-revocation-20261009.md`](hades-core-open-webui-0114-ldap-group-revocation-20261009.md).
This does not enable LDAP group management in production or qualify immediate
revocation of existing sessions.

The patched candidate also passed a disposable 0.11.1 to 0.11.4 database
migration, persistence, private-chat isolation, restart, SQLite-integrity, and
snapshot-restore rollback replay. See
[`hades-core-open-webui-0114-migration-rollback-20261009.md`](hades-core-open-webui-0114-migration-rollback-20261009.md).
Production data was not used; production remains on 0.11.1.

## Household browser acceptance — 2026-10-09

The full candidate suite was rerun against the exact patched image
`sha256:86b448b4ae005c7971f96930f8a52677ed788d8f726dfe679367cd2046e4650e`
with Playwright 1.63.0. In addition to the owner upload and chat smoke, a
separate Beta browser session verified a visible model, a model-backed reply,
absence of Alpha's private response in Beta's account, and Beta chat
persistence after reload. API acceptance also rechecked private-chat access
denial, restart persistence, Channels member posting/read-back, admin boundary,
anonymous denial, and a model mention reaching the synthetic backend.

The synthetic fixture grants model read access individually to Alpha and Beta
through Open WebUI's supported model-access endpoint. This matches the
documented household onboarding contract; it does not claim automatic LDAP
group-to-model synchronization. The first Beta browser attempt exposed that a
promoted account with no model grant has an empty model selector. After the
fixture applied the required explicit grant, the same Beta browser flow passed.
All disposable containers, volumes, browser profiles, users, and networks were
removed. Production remains unchanged.
