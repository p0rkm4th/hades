# Workspace follow-up prompt candidate

## Change

The HADES workspace instructions now tell coding follow-ups to reuse paths,
test commands, and results already established in the conversation. Discovery
is conditional on missing information. The prompt also asks the model to use
the test command in prior context or project documentation and to avoid
repeating a successful test or diff check when the workspace has not changed.
The search tool description now gives the same conditional discovery guidance.

The change preserves the owner-only authenticated workspace, `/workspace`
path boundary, untrusted-file treatment, test-after-edit requirement, and
diff-review requirement.

## Matched comparison

Two order-balanced five-turn runs compared the candidate against PLAIN using
Hermes 0.21.6, Ollama 0.40.1, Qwen3.6:35b digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536-token context, and the same rootless Docker 29.8.2 sandbox image.
The candidate ran from source `d5f909905b46738a245ca115920a81625cf8de6d`.
All four tasks passed independent test, diff-scope, source-only commit, and
clean-worktree verification.

| Measure | PLAIN | HADES candidate |
|---|---:|---:|
| Median task time | 43.33 s | 49.66 s |
| Median model calls per task | 10.5 | 12.5 |
| Median tool results per task | 6.0 | 8.5 |
| Focused-test terminal calls, two tasks | 3 | 6 |
| Explicit diff-review calls, two tasks | 0 | 2 |
| Commit tool calls, two tasks | 2 | 2 |

HADES was 6.32 seconds slower at the median. It made no `search_files` calls in
these two candidate runs (the preceding two-repeat HADES sample made two), and
it completed the explicit diff-review turn in both runs. It also made more
focused-test calls in this sample. That leaves a workflow-quality improvement
without a measured speed improvement; the sample is too small to establish
causality or owner preference.

The two-repeat baseline comparison is recorded in the [matched telemetry
follow-up](hades-core-owner-workflow-hermes0216-native-diff-replay-2026-10-08.md).
This candidate's sanitized measurements are in
[`hades-core-owner-workspace-followup-prompt-candidate-20261008.json`](../benchmarks/hades-core-owner-workspace-followup-prompt-candidate-20261008.json).

## Telemetry limitation found during follow-up

The runner's `runs_unittest` marker did not recognize Python interpreter flags
before `-m unittest` (for example, `python -B -m unittest`). Historical command
text was intentionally discarded, so the original artifact cannot be
reclassified. The classifier now handles interpreter flags and has focused
coverage. The [fresh matched replay](hades-core-owner-workspace-followup-prompt-replay-20261008.md)
shows one successful HADES unittest call per task; the old uncertainty about
repeated HADES test execution is resolved for this fixture. The corrected
telemetry does not change old tool-call totals or independent test outcomes.

## Status

Keep this prompt change as a candidate pending direct owner review and broader
coding tasks. The follow-up prompt did not produce a speed win in either
two-repeat comparison, and the new matched run still found a HADES latency gap.
This is not a usability qualification: Scotty's preference, answer quality,
deployed Open WebUI behavior, and broader coding tasks were not measured.
The later [concise native diff review replay](hades-core-owner-workspace-concise-review-candidate-20261008.md)
reduces review response length and generation time modestly, while the larger
HADES/PLAIN task-time gap remains.
