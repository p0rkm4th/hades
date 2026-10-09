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
