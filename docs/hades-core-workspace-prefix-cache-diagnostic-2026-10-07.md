# Workspace action cache diagnostic — 2026-10-07

## Question

Does HADES' longer workspace action path persist when the two comparison arms start with the same model and prompt-cache state, and what changes at the first action request?

## Method

Four counterbalanced repeats compared PLAIN STACK and HADES on the same synthetic multi-file Python diagnosis followed by “Fix it.” Both used Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B Q4_K_M digest and verified 65,536-token context, a shared supported workspace hint, native verify-on-stop, rootless Docker 29.8.2, and the same network-disabled immutable sandbox image.

Before **each** arm, the runner unloaded the Ollama model with an empty `/api/chat` request and `keep_alive=0`, confirmed the model was absent from `/api/ps`, then reloaded it with the same short `/api/generate` warmup and verified context length. This removes cross-arm prompt-cache carryover while keeping warm model state equal. The focused reset contract passes in [the benchmark control test](../scripts/test-workspace-benchmark-cache-controls.py).

The public [metrics artifact](../benchmarks/hades-core-workspace-prefix-cache-diagnostic-20261007.json) contains byte counts and aggregate measurements only. It contains no prompts, completions, file contents, tool arguments, secrets, or host paths.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median full task | 40.9 s | 55.3 s |
| Median model generations | 8.0 | 9.5 |
| Median tool results | 11.0 | 10.0 |
| Independent final test and diff checks | 4/4 passed | 4/4 passed |
| Diagnosis workspace mutations | 2/4 runs | 0/4 runs |
| First visible diagnosis progress | 18.2–18.6 s | 0.30–0.34 s |

The paired full-task HADES-minus-PLAIN differences were +14.0, +44.0, +16.4, and +9.7 seconds; PLAIN was faster in all four repeats. The outlier involved 25 HADES model generations, so the small sample has substantial model-call variance.

The controlled cold diagnosis behaved alike with respect to cache: the first generation had zero cached input tokens in both stacks in all four repeats. On the action follow-up, PLAIN reused 6,944–8,376 input tokens; HADES reused zero in all four. PLAIN kept the same eight-schema catalog across diagnosis and action. HADES changed from two schemas (3,662 bytes) to five (9,575 bytes). The paired system text shared an 11,247-byte prefix across the two stacks, while their schemas differed. This makes HADES' action schema/context transition a plausible source of the cache miss, but the measurement does not isolate schema changes from dynamic system instructions.

HADES gave immediate, truthful progress and prevented diagnosis-time workspace edits in all four runs. PLAIN exposed more tools during diagnosis and changed the workspace in two runs. The HADES timing cost and its authority benefit are both real in this fixture; this does not assign owner preference.

## Decision

Keep the dynamic catalog and read-only diagnosis boundary. Do not switch to stable schemas: earlier matched probes gained some action cache reuse but did not improve task latency or call behavior and produced invalid diagnosis calls ([prior comparison](hades-core-native-verification-canonical-recipe-mapping-20261007.md)). Keep the short progress preface, which materially improved time to visible activity here.

The next workspace optimization must reduce the first action generation's prefill cost without allowing diagnosis mutations or adding model/tool calls. Any candidate must use the per-arm cache reset, the same two-turn interaction, counterbalanced order, and independent final verification. Collect Scotty's preference separately; these synthetic timing results cannot substitute for it.

## Corrected-reset stable-schema falsification — 2026-10-07

A follow-up tested whether a stable direct workspace catalog restores action
prefix-cache reuse. It compared the same compact geometry diagnosis → “Fix it”
fixture with four counterbalanced repeats per configuration. Both used the
same Hermes 0.21.5 install, Ollama 0.40.0, Qwen3.6 35B Q4_K_M digest,
65,536-token context, per-arm unload/reload/warmup reset, supported workspace
hint, host verification mapping, rootless Docker 29.8.2 VFS, and pinned
network-disabled sandbox image. The stable candidate existed only as a
temporary patch on base `3e1663eedc7e9000c901023ad23dc6385f21a7f9`; it exposed
five schemas in both phases while `valid_tool_names` still allowed only
`read_file` and `search_files` during diagnosis. The dynamic arm used the
current two-schema diagnosis / five-schema action catalog. A pre-run attempt
was excluded after its private rootless namespace could not create the
containerd shim socket; the isolated `/run/containerd` namespace was corrected,
the real-rootless runtime contract passed, and both reported runs used that
corrected daemon.

The privacy-reviewed metrics-only results are in the [stable candidate
artifact](../benchmarks/hades-core-workspace-stable-schema-corrected-reset-20261007.json)
and [dynamic baseline artifact](../benchmarks/hades-core-workspace-dynamic-schema-corrected-reset-20261007.json).

| Measure | Stable-schema HADES | Dynamic-schema HADES |
|---|---:|---:|
| Median HADES task | 57.2 s | 45.4 s |
| Median PLAIN task in same run | 46.2 s | 36.3 s |
| Median paired HADES − PLAIN gap | 11.5 s | 9.8 s |
| Median model generations per HADES task | 15.5 | 7.0 |
| Median tool results per HADES task | 16.0 | 7.0 |
| HADES diagnosis workspace changes | 0/4 | 0/4 |
| HADES final test and diff checks | 4/4 | 4/4 |
| PLAIN diagnosis workspace changes | 2/4 | 2/4 |
| PLAIN final test and diff checks | 2/4 | 4/4 |
| HADES first action generation cached input tokens | 5,984–7,838 | 0 in all four |
| HADES invalid diagnosis tool results | 7 | 2 |

The stable catalog restored cache reuse on the first action generation, but
the HADES task took a median 11.8 seconds longer than the dynamic run and used
more than twice as many model generations and tool results. The PLAIN medians
also differed by about 9.9 seconds between runs, showing substantial local
generation variance; the paired HADES-over-PLAIN gap was slightly larger with
the stable candidate, not smaller. PLAIN also varied across the two runs:
although it changed the workspace during diagnosis in two repeats in each run,
it passed only two final checks in the stable run and all four in the dynamic
run. This is a warning against reading the small sample as a quality ranking.
HADES blocked every diagnosis-time workspace mutation in both configurations
and passed all four HADES final checks. Stable-schema HADES nevertheless produced seven invalid diagnosis
tool results, versus two in the dynamic run. The cache mechanism is now
established for this fixture, but its end-to-end product value is negative in
these samples. **Reject stable schemas as a product fix; retain the dynamic
catalog and exact phase allowlist.** This is synthetic mechanism evidence,
not an owner-preference result.
