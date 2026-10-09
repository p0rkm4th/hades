# Phase-tagged workspace workflow replay — 2026-10-09

## Method

Reran the synthetic five-turn inspect/edit/focused-test/diff-review/commit
workflow after fixing benchmark provider-phase labels. Two order-balanced pairs
used clean Hermes 0.21.6 (`818c13be`), Ollama 0.40.1, Qwen3.6 35B Q4_K_M
(`a7eb95c5…`), verified 65,536-token context, the same immutable networkless
rootless Docker sandbox, and the same multifile fixture. Both stacks received
the same workspace context hint, prompts, and per-phase sampling seeds. The
source revision was `2a799e02599a83cda38f2d3263dcbc76c4b48969`.

The benchmark now labels each provider request by the latest seeded task turn;
the prior run incorrectly labeled these workflow requests `other`. Seeds are
also paired by task phase and call ordinal. This makes this run more diagnostic
than the earlier candidate replay, but its values should not be treated as a
direct before/after estimate against that run because the seed assignment
changed.

## Results

| Measure | PLAIN STACK | HADES candidate |
| --- | ---: | ---: |
| Median whole-task time | 42.03 s | 64.89 s |
| Median model API calls | 9.0 | 13.5 |
| Median tool results | 4.0 | 9.0 |
| Tested, source-only commits | 2/2 | 2/2 |
| Review-stage tool results | 0 | 0 |
| Visible workspace schemas during review | 8 | 5 |
| Median serialized schema size | 13,479 B | 10,529 B |

All four arms passed independent test exit-code, diff-check, intended-source
scope, commit-presence, and clean-worktree checks. HADES review requests kept
`tool_choice=none`, had an empty executable tool allowlist, and emitted no tool
calls in either repeat. The lower HADES schema volume did not make its whole
workflow faster in this replay.

The clearest tool-use difference was the focused-test turn: PLAIN used one
terminal tool result in each repeat; HADES used 4 and 7 results, including
repeated file searches and reads before terminal execution. HADES' median
focused-test stage took 13.48 s, versus 4.90 s for PLAIN. HADES' median
diff-review stage took 12.11 s, while its provider request took 3.50 s median;
about 8.6 s of that stage is outside the provider timer. This replay does not
identify whether diff collection, context construction, or postprocessing
accounts for that remainder.

## Interpretation and next work

This is strong evidence of workflow friction in this seeded task, not a broad
claim about coding quality. The task sample is two pairs, the model outputs
were not reviewed for quality or naturalness, and no owner preference was
collected. PLAIN's review calls also returned no tool results, so this run does
not establish that PLAIN reviewed the actual diff. HADES supplied native Git
diff evidence while exposing no executable tools during review.

Next, profile the HADES focused-test tool loop and time the internal diff-review
path around evidence collection, context construction, and response handling.
Then test the smallest change that removes repeated discovery while preserving
test evidence and read-only review authorization. Keep this candidate
unqualified until a matched replay and direct owner review show that it helps.

Sanitized measurements: [paired replay artifact](../benchmarks/hades-core-owner-workspace-review-phase-profile-20261009.json).
