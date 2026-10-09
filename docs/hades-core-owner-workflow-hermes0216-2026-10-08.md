# Hermes 0.21.6 owner workspace workflow replay — 2026-10-08

## Scope and method

This replays the synthetic five-turn `core-25`, `core-26`, `core-28`, and
`core-31` inspect/edit/test/review/commit workflow from the current committed
source `5c87f371ebc6ce0a57e8b69ff318e04b8cb88890`. Two order-balanced
PLAIN/HADES pairs used Hermes 0.21.6, Ollama 0.40.1, Qwen3.6:35b Q4_K_M at
the same digest, verified 65,536-token context, rootless Docker 29.8.2, and the
same immutable sandbox image. Each arm received a confirmed model unload and
the same warmup. Response, command, prompt, and commit text are not retained.
The artifact contains aggregate and redacted runtime metadata only.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 46.37 s | 51.94 s |
| Median provider generations | 12 | 12 |
| Median tool results | 7.5 | 16 |
| Focused-test terminal calls | 3 | 4 |
| Explicit diff-review tool calls | 1/2 | 0/2 |
| Verified clean commits | 2/2 | 0/2 |
| Independent focused tests passed | 2/2 | 2/2 |
| Expected source only changed | 2/2 | 2/2 |

Both HADES runs made the intended one-file change and passed independent test
and scope checks. Neither completed the requested commit; each ended with an
uncommitted worktree. HADES skipped the explicit diff-review turn in both
runs, then made repeated tool calls during the commit turn without producing a
commit. PLAIN committed cleanly in both runs. Median HADES time was 5.57 s
slower and it emitted 8.5 more tool results per task. This is a reproducible
P1 workspace-completion failure on this narrow fixture, not evidence that the
entire coding path fails.

This differs from the earlier Hermes 0.21.5 replay, where both HADES commits
succeeded. Keep that result as historical evidence; do not carry it forward as
qualification for Hermes 0.21.6. The current candidate needs diagnosis and a
repeat after a behavior change.

## Limits and next action

Two synthetic pairs, one small typo fixture, and direct Hermes AIAgent calls do
not measure semantic answer quality, owner preference, long coding tasks,
Open WebUI behavior, deployed parity, or remote Git push. The two repeats are
strong enough to preserve the concrete commit failure, but not to locate its
cause or estimate general success rates. Preference labels remain unassigned.

Next: inspect sanitized per-phase tool-call metrics and runtime/tool-routing
behavior, identify the repeated commit-turn loop, then change only after a
specific cause is evidenced. Rerun this order-balanced comparison and retain
failed results. Do not report coding usability as qualified until the explicit
review and clean-commit path works reliably across a broader task sample.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-workflow-to-commit-hermes0216-20261008.json).
