# HADES workspace workflow comparison on Ollama 0.40.2

This counterbalanced two-pair synthetic workflow replay used current source
`e5016c8735a426908eb38f094372f8651a099bcd`, Hermes 0.21.6, Ollama 0.40.2,
Qwen3.6 35B Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
and verified 65,536-token context. Each arm ran the same five-stage
inspect/edit/focused-test/diff-review/commit fixture. Both used the same
isolated rootless Docker 29.8.2 daemon, immutable network-disabled sandbox,
and prewarmed isolated package-manager store. Only the HADES arm loaded the
HADES overlay and Hindsight provider. The sanitized full metrics are in
[`hades-core-owner-workspace-workflow-ollama0402-current-rootless-two-repeat-20261009.json`](../benchmarks/hades-core-owner-workspace-workflow-ollama0402-current-rootless-two-repeat-20261009.json).

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 57.05 s | 53.60 s |
| Median provider calls per task | 13.5 | 11.5 |
| Median tool results per task | 9 | 7 |
| Focused-test terminal calls across two tasks | 8 | 2 |
| Explicit Git diff tool calls in dedicated review turns | 1 | 0; authenticated diff evidence supplied by HADES |
| Verified source-only commits | 2/2 | 2/2 |
| Independent focused tests and diff checks passed | 2/2 | 2/2 |

HADES supplied authenticated, bounded Git diff evidence directly in each
dedicated review turn and disabled tool calls there by design; one HADES review
turn also read a file. HADES additionally ran explicit `git diff` commands in
non-review phases in both tasks, which may be redundant given the injected
review evidence. The model's generated review was not retained, so the review
content itself is unscored. The two samples showed task-time spread (50.15–
63.95 s PLAIN; 52.41–54.80 s HADES), so the 3.45-second median difference is
diagnostic, not a general latency claim.

## Decision and limits

This is a small positive result for this specific coding workflow: HADES
completed both tasks correctly and used fewer test invocations, provider
generations, and tool results. It does not establish that HADES is generally
preferred, that its generated explanations are better, or that live Open
WebUI and deployed authentication behave the same way. The benchmark uses a
direct Hermes agent path and synthetic project. No answer-text quality review,
owner preference, remote push, or deployed parity was measured.

The open review question is whether the native diff evidence produces a useful,
accurate explanation for Scotty, and whether explicit `git diff` commands in
other HADES stages add value. Review those behaviors in natural dogfood; do not
add benchmark-only routing or weaken the workspace authority boundary to force
a scripted score.

The initial launch before this result failed during fixture setup, before any
task turn, because the test harness linked Hermes to the Hindsight repository
root instead of the Hermes provider package nested inside that repository. The
fixture now resolves `hindsight-integrations/hermes` and validates that the
provider package exists. That setup failure was excluded from task metrics.
