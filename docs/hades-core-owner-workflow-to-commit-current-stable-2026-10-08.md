# Current stable owner workspace workflow-to-commit replay — 2026-10-08

## Scope and method

This synthetic five-turn conversation continues corpus cases `core-25`,
`core-26`, `core-28`, and `core-31` in one workspace:

1. Read `validation.py` and report the error shown for zero.
2. Fix the error-message typo.
3. Run the focused test.
4. Show what changed and whether unrelated files are in the diff.
5. Commit the verified change with a clear message.

The two order-balanced PLAIN/HADES pairs used Hermes 0.21.5, Ollama 0.40.1,
Qwen3.6:35b Q4_K_M (digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`),
verified 65,536-token context, rootless Docker 29.8.2, and the same immutable
sandbox image. The post-fix run used source revision
`b3f21bd8b107135e6127db4c4655c726a30284df`. Each task was independently
tested, its complete change scope was compared with the seed commit, and the
final Git state was checked. Only aggregate metadata is retained; response
text, command text, and commit messages are not recorded.

## Post-fix results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 59.76 s | 72.15 s |
| Median provider generations | 17.5 | 13 |
| Median tool results | 12.5 | 8 |
| Focused-test terminal calls | 5 | 4 |
| Explicit diff-review terminal calls | 0 | 1 |
| Verified clean commits | 2/2 | 0/2 |
| Independent focused tests passed | 2/2 | 2/2 |
| Only intended source changed | 2/2 | 2/2 |

Both HADES runs exposed the bounded read-only terminal, but only one called it
during the explicit diff-review turn, and neither committed. Both PLAIN runs
committed cleanly. HADES used fewer generations and tool results, but took
longer and left both tasks uncommitted. Therefore the workspace routing change
did not make this workflow usable; it is not a HADES preference win. The
current likely issue is follow-up/tool selection across turns, but this replay
does not establish a single root cause.

## Limits and next action

This is two synthetic pairs on one typo fixture through the direct Hermes
AIAgent route. It does not assess semantic answer quality, owner preference,
Open WebUI persistence, production gateway authentication, or deployed parity.
No owner preference label is assigned.

The read-only Git inspection route remains insufficient. Continue from a
minimal same-session reproducer, inspect per-turn tool availability and dispatch,
and rerun before claiming the workflow is repaired. Preserve the read-only
workspace authority boundary.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-workflow-to-commit-current-stable-20261008.json).
