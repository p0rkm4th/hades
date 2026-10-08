# Workspace diagnosis tool-scope comparison

## Result

**Qualification:** the before/after rows below used a Python 3.14 substitute sandbox because the exact pinned Hermes image was not available in the rootless daemon then. The substitute lacked `make`. These runs are useful for the read-only tool-scope prompt diagnostic, but do not support product-level conclusions about test-command failures or task latency. An exact-image follow-up is recorded below.

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

## Exact pinned sandbox follow-up

The original immutable image was restored from the existing local cache into the isolated rootless daemon and verified by digest. Its container has GNU Make, Python 3.11, and Node 20. The paired task was rerun with this exact image and the updated action instruction to consult the project test recipe.

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 41.5s | 60.3s |
| Median model API calls | 8.5 | 8.0 |
| Median tool results | 11.0 | 8.5 |
| Diagnosis turns changing workspace | 2/2 | 0/2 |
| Invalid diagnosis tool results | 0 | 1 |

Independent fixture tests and source-only diff checks passed in all four tasks. HADES recorded passing native verification evidence in one of two tasks; the other action turn made a code change without running a terminal test, so HADES correctly left it unverified. PLAIN changed files during both diagnosis turns, before the follow-up “Fix it.”

This exact-image sample still shows a substantial HADES time tax and inconsistent post-edit verification. The two repeats do not establish owner preference or a reliable latency delta. The updated prompt did not eliminate all out-of-scope diagnosis calls or guarantee test execution. Hermes verify-on-stop and the host-path mapping remain benchmark-only. See the [exact-image artifact](../benchmarks/hades-core-workspace-escalation-exact-sandbox-hermes0216-ollama0401-20261008.json) for sanitized request categories and turn-level measures.
