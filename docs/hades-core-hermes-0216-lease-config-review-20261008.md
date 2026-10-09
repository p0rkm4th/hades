# Hermes 0.21.6 lease configuration review

Date: 2026-10-08

## Decision

Retain the small HADES override of `agent.turn_facade_lease.LEASE_WAIT_SECONDS`.
Hermes 0.21.6 adds `agent.gateway_turn_lease_timeout`, but it controls a
separate process-local gateway routing lease. It does not configure the durable
cross-process database admission wait used by the turn facade.

## Evidence

- Exact Hermes release source: v0.21.6 commit
  `818c13be1dc4fd28987e1e881a9408224afd4535`.
- Candidate tests for `tests/agent/test_turn_facade_lease.py`,
  `tests/gateway/test_turn_lease.py`, and
  `tests/gateway/test_config_env_bridge_authority.py`: **25 passed** on the
  exact candidate source without the HADES overlay.
- Runtime probe against that candidate: setting
  `HERMES_TURN_LEASE_TIMEOUT=0.2` left
  `agent.turn_facade_lease.LEASE_WAIT_SECONDS` at `1800.0`; setting HADES'
  `HADES_SESSION_LEASE_WAIT_SECONDS=0.1` set the durable wait to `0.1`.
- With HADES overlay active, the same three files also passed (25 passed),
  with a pytest thread warning because the overlay starts Hermes logging outside
  the candidate test harness's guarded fixture home. The no-overlay candidate
  run is the clean upstream test result; the runtime probe establishes which
  setting controls which lease.

## Removal trigger

Remove the HADES override when Hermes provides a supported configuration path
that reaches the durable turn-facade/database admission wait, and a
cross-process regression test proves bounded admission behavior after a
client disconnect. The similarly named gateway timeout is not that path.

Production remains on Hermes 0.21.2; this is candidate evidence only and does
not qualify a production upgrade.
