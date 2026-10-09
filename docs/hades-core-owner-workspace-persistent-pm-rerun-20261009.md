# HADES workspace persistent-PM paired rerun

This two-pair `workflow-to-commit` replay uses source
`c25c17ca1688b2f40e4e19d3477800c45da4f9eb`, Hermes 0.21.6, Ollama 0.40.1,
Qwen3.6 35B digest `a7eb95c5…`, verified 65,536-token context, and the same
network-disabled rootless sandbox image in both stacks. Each arm keeps a fresh
private user/profile home; one isolated Hermes package-manager store was
prewarmed before task timing and shared across arms. Its one-time prewarm took
8.02 seconds and is recorded outside the task measurements. The sanitized
records are in [`hades-core-workspace-persistent-pm-20261009.json`](../benchmarks/hades-core-workspace-persistent-pm-20261009.json).

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 47.44 s | 54.61 s |
| Median model API calls | 11.5 | 12 |
| Median tool results | 7 | 8.5 |
| Focused-test terminal calls | 3 across 2 tasks | 2 across 2 tasks |
| Explicit diff-review tool calls | 1 | 0; diff evidence was supplied in the review turn |
| Successful commits | 2/2 | 2/2 |

All four independent test runs passed, and all four commits contained only the
expected source change and left clean worktrees. HADES remained 7.17 seconds
slower by median. No answer-quality ratings or owner preferences were
collected.

The workspace overlay's pre-model diff setup fell to a median 1.19 seconds,
down from about 7 seconds in the fresh-PM-home runner. The native Git collector
itself took 6–7 ms, confirming the environment adapter removed repeated
per-command resolution. The remaining delay is package-manager resolution in
the separate gateway process.

Incremental phase times were calculated from the runner's cumulative
per-turn timestamps:

| Phase | PLAIN STACK | HADES | HADES delta |
|---|---:|---:|---:|
| Inspect | 24.08 s | 23.56 s | −0.52 s |
| Edit | 5.58 s | 5.84 s | +0.26 s |
| Focused test | 8.69 s | 11.02 s | +2.33 s |
| Diff review | 3.85 s | 4.28 s | +0.43 s |
| Commit | 5.24 s | 9.91 s | +4.67 s |

HADES added more total tool results, with repeated file discovery/reads during
the focused-test turn and a second terminal result during one commit turn. One
Git diff also ran outside the dedicated review phase. These are the clearest
remaining task-level taxes in this workflow; the pre-model collector is no
longer the dominant one.

## Decision

Keep the scoped environment adapter: it preserves the native read-only diff
and authority contract and removes repeated package-manager lookups. The
current product gap is now the model's coding-turn behavior: repeated
discovery during focused tests and extra terminal work around commit. Measure a
targeted action-prompt change against this persistent-PM control and retain it
only if completion and source-scope verification stay intact. Direct Scotty
dogfood and broader corpus preference remain open release gates.
