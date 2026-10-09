# Current stable owner corpus edit-to-test replay — 2026-10-08

## Scope and method

This is a three-turn continuation covering corpus cases `core-25` and
`core-26` in one conversation:

1. Read `validation.py` and report the error shown for zero.
2. “Fix the typo in the error message in this file.”
3. “Run the focused test for the change we just made.”

The two order-balanced pairs used the same synthetic project, Hermes Agent
0.21.5 clean install, Qwen3.6:35b Q4_K_M, Ollama 0.40.1, verified 65,536
context, `/workspace` hint, and pinned sandbox image. Only the HADES arm loaded
the current HADES overlay. Sandboxed test containers had networking disabled
under rootless Docker 29.8.2.

The artifact records timings, tool/generation counts, exit statuses, and
booleans only. It contains no answer text, command text, or fixture contents.

## Results

| Measure | PLAIN | HADES |
| --- | ---: | ---: |
| Median three-turn task time | 40.74 s | 44.48 s |
| Median provider generations per task | 7.5 | 8.5 |
| Median tool results per task | 5.5 | 5.5 |
| Focused-test terminal calls across both tasks | 3 | 5 |
| Successful focused-test results | 2/2 tasks | 2/2 tasks |
| Inspection found the expected existing message | 2/2 | 2/2 |
| Inspection changed the workspace | 0/2 | 0/2 |
| Final independent test and diff check passed | 2/2 | 2/2 |
| Only the intended source file changed | 2/2 | 2/2 |

Both stacks eventually received an exit-0 focused-test result in each pair.
PLAIN had one exit-1 test attempt before success in one pair. HADES had one
such attempt in one pair and two in the other. HADES was 2.88 seconds faster
in the first order pair, then 10.35 seconds slower in the reverse order; the
median favored PLAIN by 3.73 seconds. The test turn adds measurable action
loop cost to both stacks, and HADES’ extra retries make its result slower in
this small sample. This exceeds the 30-second normal composed-task target.

The inspect turn left the workspace unchanged for both stacks. Each final
workspace passed an independent test and `git diff --check`; only
`validation.py` was modified. This verifies the final files, while the
exit-coded in-conversation results separately show that each assistant
eventually ran the focused test.

## Limits and follow-up

These are two synthetic order-balanced pairs for one small project. The direct
Hermes AIAgent route does not qualify Open WebUI persistence, deployed gateway
authentication, human response quality, Git commit behavior, or Scotty’s
preference. Keep owner preference unassigned. The retries and latency variance
need broader cases before changing product behavior; use this finding to
target current-source focused-test and multi-step coding replays.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-edit-to-test-current-stable-20261008.json).
