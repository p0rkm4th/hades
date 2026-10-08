# Hermes 0.21.6 staging qualification

Status: **advance in staging; hold production**.

The production pin remains Hermes 0.21.2. Candidate metadata in
[`config/versions.env`](../config/versions.env) binds Hermes 0.21.6 to its
official source URL, release commit, and SHA-256. The archive was fetched from
that URL and hashed during this qualification; it was 80,269,496 bytes with
SHA-256
`1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8`.

The official [0.21.6 release](https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6)
includes a fix for automatic Git operations that could execute repository
defined filters or hooks. Its [security regression suite](https://github.com/NousResearch/hermes-agent/blob/v0.21.6/tests/security/test_gitspawn_config_injection.py)
passed against the candidate source: **25 passed**. This exercises hostile Git
configuration through Hermes' automatic workspace, session, worktree,
recovery, and related paths. It is upstream candidate evidence, not a
production HADES deployment test.

## HADES compatibility finding

The HADES overlay previously imported Hindsight only from Hermes'
`plugins.memory.hindsight` bundled module. Hermes 0.21.6 discovers the
standalone provider through its plugin catalog. With the synthetic Hindsight
plugin installed in the test profile, the old import failed and stopped
overlay initialization before the owner/household tool-scope checks ran.

The overlay now tries the legacy bundled import first, then uses Hermes'
`import_provider_module("hindsight")` catalog API. If neither provider is
installed, initialization still fails closed. The focused HADES Grocy tool
scope suite passes against both Hermes 0.21.5 and 0.21.6 with the synthetic
Hindsight plugin. It checks owner versus household schema visibility, forged
direct calls, invalid identity, recipe reads, and confirmation mediated
serving changes.

The HADES-specific owner/household authorization gates remain necessary. This
candidate work does not remove them or the scoped MCP refresh guard.

## Remaining gates

- Exercise session continuity, MCP refresh, tool search, and authenticated
  multi-user UI behavior against the exact candidate artifact.
- Complete backup, rollback, restart persistence, and direct owner acceptance
  before any production promotion.

No production service or production version pin was changed.

## Companion rootless workspace runtime evidence (2026-10-08)

The workspace escalation runtime regression passed all 12 assertions using the
official Hermes 0.21.6 candidate source above, an isolated rootless Docker
29.8.2 daemon, RootlessKit 3.2.0, slirp4netns 1.3.6, and the immutable sandbox
image `docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d`.
It covered owner-only activation, separate subject mounts, terminal access
rooted at `/workspace`, hidden sibling host data, no default sandbox network,
truthful verification reporting, and return to the ordinary-chat tool scope
after action. Household requests made no owner-workspace model invocation.

This companion run exercised the campaign worktree at local HEAD
`f854347ec3e78e27c627289ea8903ea30908fc94`, not the code in this Hermes
candidate branch. The tested HADES files were `hermes/sitecustomize.py`
SHA-256 `8c1b22df8da054ebe2a68c55fa760256ecf6a8bf18fdf1a23edebac2af4305f6`,
`hermes/workspace.py` SHA-256
`f94e49e2774255f9991489e0eb3b8437b143bee8ec8dcb9586b34e971a3b1529`, and
the runtime test SHA-256
`499c9746cb687f9ee3116297eeda4f931161980638f3b14f17cca635db95373e`.
The test used synthetic subjects and fixtures. This qualifies sandbox and
authority behavior for that source snapshot; it does not establish model-backed
coding quality, owner usability, authenticated multi-user UI behavior, or
production readiness. Reproduce it from a clean reviewable HADES commit before
using it as a promotion gate.
