# HADES workspace environment-cache paired rerun

This reruns the two-pair synthetic `workflow-to-commit` comparison after the
context-local Git environment adapter. Its base commit is
`8c379ba86d4bcc550ebb4f97ec7d45af7d7fa5ae`; tracked source modifications were
present during the replay (SHA-256 `29eeab7d…`). The artifact records the
modified source paths and full patch hash. It used Hermes 0.21.6, Ollama 0.40.1,
Qwen3.6 35B digest `a7eb95c5…`, verified 65,536-token context, and the same
network-disabled rootless sandbox image for both arms. The full content-free
records are in [`hades-core-workspace-env-cache-rerun-20261009.json`](../benchmarks/hades-core-workspace-env-cache-rerun-20261009.json).

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 50.13 s | 58.74 s |
| Median model API calls | 12 | 11 |
| Median tool results | 8.5 | 6.5 |
| Focused-test terminal calls | 2 | 2 |
| Explicit diff-review calls | 1 | 1 |
| Successful commits | 2/2 | 2/2 |

All four independent task tests passed, all four commits stayed within the
expected source-only scope, and both stacks committed both tasks. HADES remains
8.61 seconds slower by median in this two-pair sample. No answer-quality or
owner-preference labels were collected.

During HADES diff review, median wrapper time was 11.94 seconds. The Hermes
original run consumed 4.94 seconds; HADES setup before it consumed 7.00
seconds. The optimized native collector itself took 6–7 ms, and its Git
subprocesses took about 1–2 ms each. The remaining pre-call time is the initial
package-manager environment resolution in each fresh synthetic profile. Thus
the adapter removes repeated warm lookups, but the benchmark's disposable PM
home still imposes a cold-start cost that a persistent owner profile does not
pay on every turn. This run does not establish the production steady-state
latency.

## Decision

Retain the adapter provisionally: it preserves the collector result and
read-only worktree state while reducing the persistent-profile helper median
from 2.42 seconds to 0.49 seconds. The full task pair shows HADES still loses
on latency and needs a persistent-package-state comparison before this result
can support a product claim. Next, make the benchmark reuse an isolated,
prewarmed PM runtime across arms, report cold initialization separately, and
rerun the task pair. Direct Scotty dogfood remains required.
