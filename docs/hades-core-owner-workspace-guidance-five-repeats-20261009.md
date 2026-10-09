# Five-repeat workspace guidance candidate — 2026-10-09

## Candidate and method

Tested a concise addition to the HADES workspace action prompt: when a test
command is unknown, read `README.md` or `Makefile` directly once instead of
using `search_files` only to find the command. The prompt patch SHA-256 was
`7968f4a6b270b6b9edb4289834be904c063571a1bf8c0c442172c2b5b3402c62`.

Five order-balanced PLAIN/HADES pairs used Hermes 0.21.6 (`818c13be`), Ollama
0.40.1, Qwen3.6 35B Q4_K_M (`a7eb95c5…`), verified 65,536-token context,
rootless Docker 29.8.2 with VFS storage, and the same immutable networkless
sandbox and multifile fixture. The benchmark source revision was
`9e119ee243aa8a42da9146b6b0725f0b76c66b0d`. Ten arms completed; each passed
the independent test and diff checks and changed only the intended source
file.

## Results

| Measure | PLAIN STACK | HADES candidate |
| --- | ---: | ---: |
| Median whole-task time | 52.11 s | 61.35 s |
| Median model API calls | 14 | 11 |
| Median tool results | 9 | 8 |
| Successful source-only commits | 5/5 | 4/5 |
| Focused-test terminal calls, total | 9 | 6 |

HADES searched or reread files during the focused-test turn in three of five
repeats, so the new guidance did not consistently prevent test-command
discovery. In one of five HADES diff-review turns, the model attempted a
`terminal` call despite `tool_choice=none`; Hermes rejected it with an empty
executable allowlist, so no command ran. HADES committed one fewer task than
PLAIN and remained 9.24 seconds slower by median.

## Decision

Reject this prompt candidate. Fewer model calls and focused-test terminal
calls did not offset the latency and completion gap, and the review model still
attempted a tool call in one repeat. The focused runtime contract passed,
including the real rootless, network-disabled sandbox and household/subject
workspace boundaries. Those safety passes do not qualify the usability
change.

The next investigation should measure HADES time within workspace setup,
tool execution, diff collection, prompt construction, and postprocessing. The
phase profile shows request-boundary timing is insufficient to explain the
remaining task time. Do not keep additional prompt instructions on the basis
of this result.

Sanitized measurements: [five-repeat paired replay](../benchmarks/hades-core-owner-workspace-guidance-five-repeats-20261009.json).
