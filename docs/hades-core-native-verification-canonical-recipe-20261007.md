# Hermes native verification with a canonical project recipe — 2026-10-07

## Finding

The earlier synthetic workspace mapping comparison did not include a canonical
project test command. I added the same `make test` recipe and README instruction
to both PLAIN and HADES coding fixtures. Hermes 0.21.5's project-facts detector
recognizes `make test`, and its native evidence ledger can record a passing run
against that recipe.

A private synthetic contract probe exercised the Hermes 0.21.5 evidence APIs
with a real local `make test` subprocess. It observed a `passed` status for the
originating session, `unverified` for a different session, `stale` after a new
edit, a stop nudge while evidence was missing or stale, and `passed` again after
fresh evidence. The probe retained no prompts, responses, tool arguments, or
fixture contents.

Hermes' focused upstream suites also passed:

```text
tests/agent/test_verification_evidence.py
tests/agent/test_verification_stop.py
tests/agent/test_verification_continuation_budget.py
47 passed in 5.18s
```

## Limits and decision

This was a direct project-facts/ledger contract probe, not a model-backed HADES
gateway run. It does not establish that Hermes' real terminal result packaging
records evidence under HADES' Docker `/workspace` mount, or that the model
reliably runs `make test` after editing. A matched model-backed rerun was held
because the required rootless Docker VFS had only 48 MiB free on its 32 GiB
temporary filesystem; no container store was changed.

The result narrows the open issue: native Hermes recognizes a canonical recipe
and enforces session/freshness semantics in its ledger. Production adoption
remains unjustified until a model-backed PLAIN/HADES pair proves that mutation
paths and terminal evidence resolve to the same canonical workspace and that
fresh test evidence appears after the final edit. Keep the current truthful
unverified report and diagnosis mutation boundary meanwhile.
