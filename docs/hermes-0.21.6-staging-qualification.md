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

- Run the HADES workspace regression against a real rootless sandbox with the
  exact candidate. Rootless Docker was unavailable in this qualification; the
  host's rootful Docker correctly remains ineligible for workspace actions.
- Exercise session continuity, MCP refresh, tool search, and authenticated
  multi-user UI behavior against the exact candidate artifact.
- Complete backup, rollback, restart persistence, and direct owner acceptance
  before any production promotion.

No production service or production version pin was changed.
