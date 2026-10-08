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
gate. A matched two-repeat stable-schema experiment on the same geometry
escalation fixture kept all five workspace schemas present in both HADES
phases, while `valid_tool_names` continued to allow only read/search during
diagnosis. The diagnosis mutation attempt in that arm was rejected and neither
diagnosis workspace changed. HADES median task time was 44.64 seconds, with 11
model API calls and 11 tool results; its matched PLAIN arm was 30.89 seconds,
with 7 calls and 8 tool results. The dynamic-schema rerun measured HADES at
42.36 seconds, 6 calls, and 6 tool results versus PLAIN at 28.85 seconds, 9
calls, and 10 tool results. Every action passed independent tests and diff
checks. The schema-stability candidate therefore did not improve HADES latency
or calls in this fixture and remains rejected as a product fix. The persistent
roughly 13.5-second gap points to other HADES workspace-path costs; these small
samples do not isolate their causes or qualify owner preference. Details are
in [`hades-core-workspace-stable-schema-probe-20261007.json`](../benchmarks/hades-core-workspace-stable-schema-probe-20261007.json).

Following that rejection, the benchmark-only
`HADES_BENCHMARK_STABLE_WORKSPACE_SCHEMAS` switch and its alternate
prompt/catalog branch were removed from `hermes/sitecustomize.py`, the
workspace benchmark runner, and its runtime contract. The default dynamic
catalog and exact per-turn `valid_tool_names` boundary remain. Historical
measurements stay available in the artifacts; rerunning the rejected prototype
no longer requires shipping an experiment hook in the active overlay.

The earlier canonical-recipe dynamic-schema pair measured HADES about 22.5
seconds slower overall than PLAIN and exceeded the 30-second composed-task
target, despite correct final tests and authority boundaries. Both benchmark
runs are diagnostic, not general performance or quality qualifications.
