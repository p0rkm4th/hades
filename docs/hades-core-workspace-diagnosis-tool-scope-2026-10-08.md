# Workspace diagnosis tool-scope comparison

## Result

A clearer read-only instruction removed the out-of-scope tool results seen in the HADES diagnosis arm. Before the change, HADES returned three invalid tool results across two tasks: two `terminal` requests and one `patch` request were outside the read-only catalog. After the change, HADES returned no invalid diagnosis tool results. PLAIN returned none in either pair.

This is a narrow model-backed diagnostic, not an owner-preference result. Both runs used only two order-balanced task repetitions, and latency varied substantially between repetitions. The measurements do not establish that the wording change improved latency or overall task quality.

| Measure | Before | After |
|---|---:|---:|
| HADES invalid diagnosis tool results | 3 | 0 |
| HADES diagnosis turns that changed workspace | 0/2 | 0/2 |
| PLAIN diagnosis turns that changed workspace | 1/2 | 1/2 |
| Independent fixture tests passed | 4/4 | 4/4 |
| HADES median task time | 61.5s | 55.6s |
| PLAIN median task time | 52.9s | 63.3s |

PLAIN also attempted three mutations during diagnosis before the change and one afterward; its writable tools allowed a diagnosis-turn workspace change in one of two tasks in both samples. This demonstrates the value of HADES' read-only boundary for an explanation request. The HADES task-time change is not attributed to the prompt edit: the sample is small and model variance is visible in the PLAIN results.

## Change

Read-only workspace turns now state that only `read_file` and `search_files` are available, explicitly forbid calls to `terminal`, `patch`, and `write_file`, and describe how to handle insufficient evidence. The runtime contract pins this language while continuing to expose only the two read tools.

## Method and limits

Both paired runs used Hermes 0.21.6, Ollama 0.40.1, Qwen3.6 35B with the same model digest, 65,536-token context, rootless Docker 29.8.2 with VFS, and the same immutable Python sandbox image. Per-arm model cache was reset and warmed identically; task containers had no network. The task was a synthetic multifile Python diagnosis followed by a fix. A benchmark-only workspace verification mapping was enabled; it is not production HADES code.

Hermes native verify-on-stop was also enabled experimentally in both arms. It generated two stop nudges for each HADES task, while the mapped native evidence was absent or failed in the recorded snapshots. Independent tests passed in all four final workspaces, but this does not validate Hermes' native evidence ledger. Keep the native verification experiment out of production pending a correct canonical workspace/session mapping and a larger matched sample.

See the [before artifact](../benchmarks/hades-core-workspace-escalation-readonly-tool-scope-hermes0216-ollama0401-20261008.json) and [after artifact](../benchmarks/hades-core-workspace-escalation-readonly-tool-scope-hermes0216-ollama0401-after-20261008.json) for sanitized turn-level counts. Prompts, responses, tool arguments, and fixture contents are excluded.
