# Canonical test recipe and native workspace verification — 2026-10-07

## Method

Ran two order-balanced synthetic diagnosis → action pairs through clean Hermes
0.21.5 and the HADES overlay. Both arms used Ollama 0.40.0, the same Qwen3.6
35B Q4_K_M digest, verified 65,536-token context, the same rootless Docker
29.8.2 VFS runtime, the same immutable sandbox image digest, and the same
workspace context hint. Task containers used `network=none`. The project
advertised the same canonical `make test` recipe in both arms. Native
verify-on-stop was enabled in both; a benchmark-only mapping connected the
container `/workspace` path to the synthetic host project root for Hermes'
verification ledger.

The metrics-only artifact is
[`hades-core-native-verification-canonical-recipe-mapping-20261007.json`](../benchmarks/hades-core-native-verification-canonical-recipe-mapping-20261007.json).
It retains no prompt or response text, tool arguments, fixture contents, or
local filesystem paths.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 30,968 ms | 53,459 ms |
| Median model generations | 9.0 | 9.5 |
| Median tool results | 11.5 | 12.0 |
| Median action phase | 7,402 ms | 21,710 ms |
| Diagnosis/action schemas | 8 / 8 | 2 / 5 |
| Cached input tokens on first diagnosis generation | 5,448 / 5,448 | 0 / 0 |
| Cached input tokens on first action generation | 7,338–7,758 | 0 / 0 |

All four action turns recorded fresh passing evidence for the canonical test
recipe. Independent unittest runs and `git diff --check` passed in all four
final workspaces; each had only the expected source file changed. Hermes
reported the native evidence as `passed` for all four sessions, with no stop
nudge needed. HADES
rejected two attempted diagnosis-time mutations, and no diagnosis turn changed
the workspace.

HADES had zero cached input tokens on the first generation in both diagnosis
turns and both action follow-ups. PLAIN reused 5,448 cached input tokens on
both first diagnosis generations and 7,338–7,758 on the action follow-ups.
Therefore, the cache gap is present before HADES changes from two diagnosis
schemas to five action schemas; the schema transition cannot explain the whole
gap. The transition coincided with the action-phase cache miss, but this sample
does not isolate its effect from other differences in HADES request or prompt
construction. The action phase took about 14.3 seconds longer in HADES at the
median. Treat cache non-reuse as a measured HADES tax and the schema transition
as one unproven contributor, not the established cause.

An earlier two-repeat
[stable-schema candidate v5](../benchmarks/hades-core-owner-coding-escalation-hermes0215-ollama040-v5.json)
kept five schemas in both HADES phases and left only read/search executable
during diagnosis. In that separate fixture, both first action generations
reused about 4.8k cached tokens and the first patch calls took about 3.1
seconds, versus 13.6 seconds in its dynamic-schema baseline. HADES still took
27.50 seconds median versus PLAIN's 21.25 seconds, and its first diagnosis
could still pay a cold-prefix cost. This is promising mechanism evidence, not
a qualified fix; the fixture and protocol differ from the canonical-recipe
pair above.

## Decision and limits

The canonical-recipe follow-up verifies that Hermes' real terminal-result path
can record fresh evidence against the mapped project root in this fixture. The
earlier evidence-ledger contract probe covers missing/stale evidence and
session isolation. Neither result qualifies the deployed gateway or proves
owner preference.

Keep native verify-on-stop out of production until the smallest supported
workspace mapping is proven in the deployed path. Keep the diagnosis mutation
gate. Investigate HADES prompt/request construction and cache non-reuse before
isolating the diagnosis-to-action schema transition. Re-run the stable-schema
candidate on the current canonical-recipe fixture with a matched PLAIN arm,
and capture the first-use as well as follow-up cache counts. Preserve the
read-only `valid_tool_names` gate and reject the candidate if diagnosis
mutation attempts or completion quality regress. HADES was about 22.5 seconds
slower overall in the dynamic-schema pair and exceeded the 30-second
composed-task target, despite correct final tests and authority boundaries.
The small synthetic samples are diagnostic, not a general performance or
quality qualification.
