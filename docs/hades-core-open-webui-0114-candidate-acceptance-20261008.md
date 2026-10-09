# Open WebUI 0.11.4 candidate acceptance

Date: 2026-10-08

## Tested artifact

- Local immutable image ID: `sha256:110d8c280b165eeb26bc5c5bad0dce675b376399f18e04954f71e6338f596469`
- Local repository digest: `hades-open-webui@sha256:110d8c280b165eeb26bc5c5bad0dce675b376399f18e04954f71e6338f596469`
- Upstream Open WebUI version label: `0.11.4`
- Upstream source revision label: `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`
- HADES asset/compatibility source revision label: `e33b7d18c889775260e5ace804aac0ebf598d8d8`
- Base image label: `ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f`

The immutable local image ID was passed directly to
`scripts/test-open-webui-candidate.sh`; production pins and services were not
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

Candidate containers, volumes, and networks were absent after the acceptance
script completed.

## Qualification boundary

This passes the script's synthetic private-chat and Channels acceptance for
this exact image. It is not owner-visible UI acceptance or production
promotion. The image's HADES source label is an earlier revision than the
current review branch; re-build and repeat against the proposed exact promotion
artifact. LDAP/group provisioning behavior, theme/assets in a browser, file
upload and file-picker behavior, shared-folder behavior, full migration and
rollback, and reconstructed-deployment acceptance remain open. Keep production
at 0.11.1 until those gates pass and provenance is recorded for the promotion
artifact.
