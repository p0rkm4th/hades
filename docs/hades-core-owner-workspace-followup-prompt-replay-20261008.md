# Matched workspace follow-up replay — 2026-10-08

## Method

Two order-balanced five-turn synthetic `workflow-to-commit` runs compared PLAIN
Hermes with the current HADES workspace overlay. Both arms used Hermes 0.21.6,
Ollama 0.40.1, Qwen3.6:35b digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536 context, and the same pinned Python/Node sandbox image. The daemon was
Docker 29.8.2 in rootless mode with the VFS storage driver. Containers ran with
network disabled. The scenario used the multifile `error_message` fixture.
Before each arm, the benchmark unloaded and identically rewarmed the model.

The runner records tool names, call counts, output markers, token counts,
latencies, and independent checks; it does not store prompts, responses,
commands, or tool-result text. All four task workspaces passed independent
unittest, diff-check, source-only change, commit, and clean-worktree checks.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 48.71 s | 64.35 s |
| Median model API calls per task | 12.5 | 11.0 |
| Median tool results per task | 8.0 | 8.0 |
| Focused-test terminal calls, two tasks | 4 | 2 |
| Explicit diff-review terminal calls, two tasks | 2 | 0 |
| Commit-stage tool calls, two tasks | 2 | 3 |
| Independent tasks verified | 2/2 | 2/2 |

HADES was 15.64 seconds slower at the median (32% in this two-repeat sample),
while making fewer model calls and the same median number of tool calls. Its
focused-test stage ran the documented unittest once in each task. PLAIN made
four focused-stage terminal calls, of which two had unittest output markers;
the command text is not retained, so the other calls cannot be classified
reliably.

The HADES focused-test stages also made 3 and 4 search/read calls, respectively.
The PLAIN stages made 0 and 3 such calls. This is a small sample, but HADES
still spends discovery effort on a follow-up test request despite the prompt
instructing it to reuse established paths and commands.

The clearest time difference was diff review. Median stage time was 19.62 s for
HADES and 5.00 s for PLAIN. HADES used the authenticated native diff with zero
tools exposed, but its review answer requests took 9.37 and 10.83 seconds and
returned 92 and 170 completion tokens. Those requests had zero tool schemas.
The evidence points to review-answer generation as a major remaining HADES tax;
it does not establish that the review content was more useful. HADES commit
stage median was 7.23 s versus 4.85 s for PLAIN, another area to inspect.

| Phase duration | PLAIN median | HADES median |
|---|---:|---:|
| Inspect | 23.76 s | 22.21 s |
| Edit | 5.65 s | 5.82 s |
| Focused test | 9.44 s | 9.47 s |
| Diff review | 5.00 s | 19.62 s |
| Commit | 4.85 s | 7.23 s |

Durations are derived by subtracting adjacent cumulative phase timestamps in
each run. Two observations do not establish stable population effects.

## Status

This replay corrects the previous uncertainty about repeated HADES test
execution: both HADES runs invoked the test once and passed. A content-free
classifier fix now recognizes Python interpreter flags such as `-B`; old
artifacts cannot be reclassified because their commands were deliberately
omitted. No owner preference, answer-quality review, Open WebUI flow, or
production parity was measured. HADES usability remains unqualified.

Sanitized telemetry: [`hades-core-owner-workspace-followup-prompt-replay-20261008.json`](../benchmarks/hades-core-owner-workspace-followup-prompt-replay-20261008.json).
