# HADES Core workspace escalation comparison — clean worktree v2

Date: 2026-10-08
Base revision: `8581de336ed793dacb6d1c2024e7d1138b0a6e31`
Tested overlay/source hashes: recorded in [`hades-core-workspace-escalation-hermes0216-ollama0401-clean-v2.json`](../benchmarks/hades-core-workspace-escalation-hermes0216-ollama0401-clean-v2.json)

## Method

Two order-balanced repeats compared clean Hermes 0.21.6 (PLAIN STACK) with the HADES overlay loaded from the isolated worktree. Both used Ollama 0.40.1, Qwen3.6 35B digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, 65,536 context, reasoning disabled, and the same rootless Docker 29.8.2 daemon and immutable sandbox image. Each repeat used the same synthetic failing geometry project and the same two-turn prompt: diagnose, then “Fix it.” An independent test run and Git diff check followed each task.

The output retains sanitized tool names/shape and timings, not provider request bodies or file contents. The exact worktree source hashes are included because this run tested uncommitted overlay changes.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 26.73s | 44.08s |
| Median model calls per task | 6.5 | 7.0 |
| Median tool results per task | 5.5 | 7.0 |
| Diagnosis workspace changes | 2/2 | 0/2 |
| Independent tests passed | 4/4 | 4/4 |
| Expected source only changed | 2/2 | 2/2 |

PLAIN STACK was faster in this sample. HADES avoided the premature diagnosis edits seen in both PLAIN runs, but paid an action-time cost and averaged more model calls/tool results. This supports keeping the read-only diagnosis boundary while investigating the action loop's latency and tool/generation overhead.

## Limits

This is a two-repeat synthetic coding fixture, not a realistic owner corpus or preference study. It tests direct AIAgent turns, not Open WebUI persistence or deployed authentication. It does not qualify long coding tasks, Git commits, ordinary chat, memory, household flows, or direct Scotty preference. The benchmark cannot establish general HADES usability from this sample.
