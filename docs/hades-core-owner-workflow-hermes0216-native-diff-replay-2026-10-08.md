# Hermes 0.21.6 workspace native diff replay — 2026-10-08

## Change under evaluation

Hermes 0.21.6 provides a hardened `tools.working_diff.collect_working_diff` helper for its native `/diff` surfaces. HADES now calls that helper only for an authenticated owner read-only diff-review turn after recent workspace work. The response is bounded to 24,000 characters, identifies truncation, and marks project text as untrusted evidence. The review model receives no tool schemas, `tool_choice` is set to `none`, and prior tool-call/tool-result messages are removed from that review turn's prompt while user/assistant conversation text remains. Later action turns restore normal workspace tools. The underlying Git workspace is never modified by diff collection.

The focused rootless workspace contract passes. It verifies the diff context includes tracked and untracked changes, reads the workspace's actual Git state, leaves that state unchanged, and is activated only for contextual review requests.

## Matched workflow

Two order-balanced synthetic five-turn workflows (`core-25`, `core-26`, `core-28`, `core-31`) ran against source `3e15d5d26523f1cb1ac86f21c8ce91ae4326e5fa`. Both arms used Hermes 0.21.6, Ollama 0.40.1, the same Qwen3.6:35b Q4_K_M digest, verified 65,536-token context, and pinned rootless sandbox image. Model cache was unloaded and identically warmed before every arm. The artifact retains aggregate timings, token/tool metadata, and booleans for diff-context presence; it does not store prompts or responses.

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 46.70 s | 66.19 s |
| Median model API calls per task | 12.5 | 13.5 |
| Median tool results per task | 9.0 | 10.0 |
| Focused tests passed | 2/2 | 2/2 |
| Intended source only | 2/2 | 2/2 |
| Verified clean commits | 2/2 | 2/2 |
| Native diff context in explicit review | 0/2 | 2/2 |
| Review-turn tools exposed/called | 0/2 | 0/2 |

The HADES native diff evidence was complete in both review turns. Both HADES runs committed cleanly, and their focused tests passed. This closes the specific terminal-activation and missed-commit failure on this fixture. HADES was 19.48 seconds slower at the median (about 42%) in this small sample, so this is not a net usability win yet. The benchmark cannot rate the generated review explanations because it deliberately retains no response text; direct owner review is required.

## Status

This is partial synthetic evidence. It is not deployed Open WebUI acceptance, broad coding qualification, or Scotty preference. The HADES overlay's system context remains roughly 1.1 KB larger than PLAIN for the workspace stages. Focused-test tool calls and generation latency deserve the next profile. The owner corpus still has 29/55 cases without direct replay and no preference labels.

Sanitized measurements: [`hades-core-owner-workflow-hermes0216-3e15d5d2.json`](../benchmarks/hades-core-owner-workflow-hermes0216-3e15d5d2.json).
