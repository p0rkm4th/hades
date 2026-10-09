# Hermes 0.21.6 tool search and HADES scope review

Date: 2026-10-08

## Finding

Hermes 0.21.6 has native deferred-tool discovery through `tool_search`,
`tool_describe`, and `tool_call`. HADES does not need a second general-purpose
discovery layer. The remaining HADES bridge adapter enforces authenticated
owner/household scope after Hermes rebuilds its deferred catalog from enabled
toolsets, and keeps the generic Grocy serving mutation out of both discovery
and dispatch. Removing this boundary would make filtered eager schemas
insufficient as an authorization control.

## Candidate evidence

- Exact Hermes source: v0.21.6 commit
  `818c13be1dc4fd28987e1e881a9408224afd4535`.
- `scripts/test-grocy-tool-scope-hermes-runtime.sh` passed against that
  candidate's Python environment with its staged Hindsight provider plugin
  mounted into the disposable test profile.
- The run verified deferred catalog reconciliation, owner versus household
  recipe visibility, denial before handler dispatch for a forged owner-only
  call, direct in-scope recipe calls, and preview/cancel/stale-preview behavior
  for the serving-change flow.
- The test uses synthetic tool handlers and isolated in-memory HTTP fixtures.
  It establishes the adapter boundary against the exact Hermes runtime; it is
  not production Grocy or household acceptance.

## Decision

Retain the narrow authorization adapter and native Hermes tool-search
primitives. Do not recreate discovery in HADES. A future deletion requires
upstream to provide an authenticated, per-turn filtered deferred catalog and
dispatch boundary, with the same cross-scope regression checks passing without
the HADES patch.

The test script now accepts
`HADES_HERMES_TEST_HINDSIGHT_PLUGIN_DIR` so exact Hermes candidates can load the
provider in their disposable profile without reading a production Hermes
home. The variable is optional; normal runs remain isolated and unchanged.
