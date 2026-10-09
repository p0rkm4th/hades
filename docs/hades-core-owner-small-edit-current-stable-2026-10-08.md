# Current stable owner corpus small-edit replay — 2026-10-08

## Scope and method

This directly replays owner corpus case `core-25` as a natural follow-up in
the same conversation. First, the assistant reads `validation.py` and reports
the error for zero; then the user says, “Fix the typo in the error message in
this file.” Each arm starts from the same synthetic project and clean
Hermes Agent 0.21.5 install. PLAIN uses native Hermes tools; HADES loads the
current HADES overlay. Both use Ollama 0.40.1, Qwen3.6:35b Q4_K_M
(`a7eb95c5…`), a verified 65,536-token context, the same `/workspace` hint,
and the same immutable sandbox image under rootless Docker 29.8.2. The two
order-balanced pairs were PLAIN→HADES and HADES→PLAIN.

The artifact stores timings, call/tool counts, schema metrics, booleans, and
test status only. It contains no answer text or fixture contents.

## Results

| Measure | PLAIN | HADES |
| --- | ---: | ---: |
| Median two-turn task time | 32.19 s | 28.45 s |
| Median provider generations | 5.5 | 4 |
| Median tool results | 3.5 | 2 |
| Inspection found the expected existing message | 2/2 | 2/2 |
| Inspection changed the workspace | 0/2 | 0/2 |
| Final test and diff check passed | 2/2 | 2/2 |
| Only the intended source file changed | 2/2 | 2/2 |

HADES read the named file directly in both inspection turns. PLAIN searched
twice before reading it in one pair, while it read directly in the other. Both
stacks waited for the explicit edit request before changing the workspace.
The measured task medians favor HADES by 3.74 seconds, with fewer generations
and tool results in this small sample. Task times were 35.75 and 28.64 seconds
for PLAIN, and 29.23 and 27.67 seconds for HADES; therefore order and local
model variance remain material. First streamed deltas on inspection arrived
at 22.14–29.49 seconds for PLAIN and about 0.30 seconds for HADES, followed by
the tool/model work needed to finish each turn.

## Limits and follow-up

This is two synthetic pairs for one small edit, through direct Hermes AIAgent
instances. The independent test was run after the interaction; the task did
not ask the assistant to run it. The replay does not measure Open WebUI
persistence, deployed gateway authentication, human answer quality, Git
commit behavior, or Scotty’s preference. Keep the preference label unassigned.
The result supports continuing the small-edit and follow-up cases in the
comparative corpus, not declaring coding usability qualified.

Artifact: [sanitized comparative metrics](../benchmarks/hades-core-owner-small-edit-current-stable-20261008.json).
