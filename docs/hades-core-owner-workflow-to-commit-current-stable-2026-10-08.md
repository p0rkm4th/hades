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
sandbox image. The synthetic Git project ignores Python bytecode equally in
both arms. Each task was independently tested, its complete change scope was
compared with the seed commit, and the final Git state was checked. Only
aggregate metadata is retained; response text, command text, and commit messages
are not recorded.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 59.12 s | 49.84 s |
| Median provider generations | 17.5 | 11 |
| Median tool results | 13 | 13.5 |
| Focused-test terminal calls | 4 | 4 |
| Explicit diff-review calls | 2 | 0 |
| Verified clean commits | 2/2 | 0/2 |
| Independent focused tests passed | 2/2 | 2/2 |
| Only intended source changed | 2/2 | 2/2 |

Each stack needed one exit-1 focused-test attempt before a passing retry in each
pair. HADES also made a patch-tool call in the commit follow-up in both pairs.
Its commit-stage terminal calls returned three `tool_not_found` errors across
the two tasks. One HADES task ran a Git diff command during the commit turn;
neither made a diff call in response to the explicit review request. PLAIN
reviewed the diff and committed in both tasks. No HADES commit was verified.

HADES was faster in this small sample, but it did not complete the requested
workflow. This is not a HADES preference win. The code currently narrows
read-only workspace requests to `read_file` and `search_files`, excluding the
terminal needed for Git diff inspection; this is a plausible contributor to the
missed review step. The terminal `tool_not_found` failures during commit need a
separate dispatch investigation before attributing their cause.

## Limits and next action

This is two synthetic pairs on one typo fixture through the direct Hermes
AIAgent route. It does not assess semantic answer quality, owner preference,
Open WebUI persistence, production gateway authentication, or deployed parity.
No owner preference label is assigned.

Next, inspect the read-only workspace tool boundary and terminal dispatch on a
minimal reproducer. Preserve read-only workspace authority while enabling
bounded Git review, then rerun this full conversation and direct Scotty
dogfood before calling the action workflow usable.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-workflow-to-commit-current-stable-20261008.json).
