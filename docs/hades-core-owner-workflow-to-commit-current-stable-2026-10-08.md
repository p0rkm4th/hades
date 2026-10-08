# Current stable owner workspace workflow-to-commit replay — 2026-10-08

## Scope and method

This synthetic five-turn conversation continues corpus cases `core-25`,
`core-26`, `core-28`, and `core-31` in one workspace:

1. Read `validation.py` and report the error shown for zero.
2. Fix the error-message typo.
3. Run the focused test.
4. Show what changed and whether unrelated files are in the diff.
5. Commit the verified change with a clear message.

Two order-balanced PLAIN/HADES pairs used Hermes 0.21.5, Ollama 0.40.1,
Qwen3.6:35b Q4_K_M (digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`),
verified 65,536-token context, rootless Docker 29.8.2, and the same immutable
sandbox image. The current run used source revision
`75241cfa96602142ef3776b4b2f9c28efec5586c`. Each task was independently
tested, its complete change scope was compared with the seed commit, and the
final Git state was checked. Only aggregate metadata is retained; response
text, command text, and commit messages are not recorded.

## Current results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 62.80 s | 62.30 s |
| Median provider generations | 18 | 13 |
| Median tool results | 13.5 | 8.5 |
| Focused-test terminal calls | 6 | 3 |
| Explicit diff-review calls | 2/2 | 1/2 |
| Tasks with diff inspection before commit | 2/2 | 2/2 |
| Verified clean commits | 2/2 | 2/2 |
| Independent focused tests passed | 2/2 | 2/2 |
| Diff checks passed | 2/2 | 2/2 |
| Only intended source changed | 2/2 | 2/2 |

HADES completed both tasks after the workspace follow-up routing repair. The
first repaired run inspected the diff in response to the explicit review turn;
the second skipped a tool call on that turn, then inspected the diff immediately
before its commit. That is a remaining conversation-timing miss even though the
change was reviewed before either commit. Both stacks passed the independent
test, changed only the intended file, and left a clean committed worktree.

On this small sample HADES used five fewer median model generations and five
fewer median tool results than PLAIN, with roughly equivalent task time. These
measurements do not establish owner preference or answer quality. The earlier
post-review-routing replay failed both HADES commits because accumulated
"what changed" wording routed the final turn to the homelab activity catalog;
the validation diagnostic showed no workspace tools were executable then.
The current fix carries an explicit workspace task into a natural mutation
follow-up and prevents historical homelab wording from overriding it. That
failure is preserved in the [intermediate replay artifact](../benchmarks/hades-core-owner-workflow-to-commit-after-git-review-route-20261008.json).

## Limits and next action

This is two synthetic pairs on one typo fixture through the direct Hermes
AIAgent route. It does not assess semantic answer quality, owner preference,
Open WebUI persistence, deployed parity, or direct Scotty dogfood. No owner
preference label is assigned.

Next, improve the missed explicit review-turn behavior if owner use confirms it
causes friction, and continue the full realistic corpus and direct owner
qualification. The workspace action route is not yet generally usability
qualified.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-workflow-to-commit-current-stable-20261008.json).
