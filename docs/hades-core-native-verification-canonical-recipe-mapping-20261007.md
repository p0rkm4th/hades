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
| Cached input tokens on first action generation | 7,338–7,758 | 0 / 0 |

All four action turns recorded fresh passing evidence for the canonical test
recipe. Independent unittest runs and `git diff --check` passed in all four
final workspaces; each had only the expected source file changed. Hermes
reported the native evidence as `passed` for all four sessions, with no stop
nudge needed. HADES
rejected two attempted diagnosis-time mutations, and no diagnosis turn changed
the workspace.

The HADES schema transition from two diagnosis schemas to five action schemas
coincided with a prompt-cache miss on both action follow-ups. PLAIN kept eight
schemas throughout and reused 7,338–7,758 cached input tokens on its first
action generation. The action phase took about 14.3 seconds longer in HADES at
the median. This is the strongest measured HADES tax in this sample; the pair
does not isolate the schema transition as its sole cause.

## Decision and limits

The canonical-recipe follow-up verifies that Hermes' real terminal-result path
can record fresh evidence against the mapped project root in this fixture. The
earlier evidence-ledger contract probe covers missing/stale evidence and
session isolation. Neither result qualifies the deployed gateway or proves
owner preference.

Keep native verify-on-stop out of production until the smallest supported
workspace mapping is proven in the deployed path. Keep the diagnosis mutation
gate. Investigate the diagnosis-to-action schema transition and cache miss as a
usability bottleneck: HADES was about 22.5 seconds slower overall and exceeded
the 30-second composed-task target, despite correct final tests and authority
boundaries. This two-pair synthetic sample is diagnostic, not a general
performance or quality qualification.
