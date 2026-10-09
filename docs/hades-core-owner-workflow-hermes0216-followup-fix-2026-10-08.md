# Hermes 0.21.6 workspace follow-up and commit replay — 2026-10-08

## Diagnosis

The failed Hermes 0.21.6 replay at source `16d340775f55e9fc56fc809fadea46d18c817a1d` recorded empty workspace schemas and an empty executable workspace catalog when HADES attempted tools during the commit turn. The natural follow-up “Commit the change we just verified with a clear message.” was not recognized by `is_workspace_request`, even when recent conversation history was about editing and testing a project. It therefore reached HADES' ordinary-turn path, which deliberately clears inherited tool schemas. The model then emitted unavailable workspace calls.

A context-gated recognition rule now activates workspace capability for explicit actions referring to “this/that/the change, fix, work, or result” only when recent history contains workspace work. It does not activate for the same phrase without that history. The authenticated owner/rootless runtime contract passed, including subject isolation and denied household access.

## Post-fix comparison

The same two order-balanced synthetic five-turn `core-25`, `core-26`, `core-28`, and `core-31` workflows ran against committed source `04c05fdb1d2a3aebd63b757ac6302cf12d858048`. Arms used Hermes 0.21.6, Ollama 0.40.1, the same model/digest and verified 65,536-token context, and the same immutable rootless sandbox image. The benchmark unloaded and identically warmed Ollama before every arm. No prompt, answer, command, or commit text is retained.

| Measure | PLAIN | HADES after fix |
|---|---:|---:|
| Median task time | 42.22 s | 45.68 s |
| Median provider generations | 11 | 12.5 |
| Median tool results | 6 | 15.5 |
| Focused tests passed | 2/2 | 2/2 |
| Intended source only | 2/2 | 2/2 |
| Verified clean commits | 2/2 | 2/2 |
| Explicit diff-review tool calls | 1/2 | 0/2 |
| Diff inspections during commit turn | 0/2 | 2/2 |

This fixes the repeated HADES commit failure on this fixture. HADES still took 3.46 seconds longer at the median and returned 9.5 more tool results per task. In both HADES runs the dedicated review turn made no tool call; the diff was inspected later during the commit turn. That preserves a before-commit check but misses the requested conversational sequence. The run does not establish answer quality or owner preference.

## Qualification and next action

Workspace action-on-follow-up is improved but not generally qualified. Keep the explicit review-turn timing as an open friction item. Review evidence available to the agent during the read-only turn is limited to native file/search tools; compare whether the model can accurately summarize the earlier patch result, and determine whether safe read-only Git inspection can use an upstream-native capability. Do not grant a general shell on read-only turns to fix this gap.

The pre-fix empty-catalog diagnostic is preserved in the [reproduction metrics](../benchmarks/hades-core-owner-workflow-hermes0216-empty-catalog-20261008.json). The post-fix matched results are in the [comparative metrics](../benchmarks/hades-core-owner-workflow-hermes0216-followup-fix-20261008.json). The earlier Hermes 0.21.5 pass remains historical evidence only.
