# HADES workspace diff-review Git environment profile

This content-free profile isolates the setup time before Hermes' original
`AIAgent.run_conversation` call during the `review_diff` stage. It was run on
source `38191ed7261ade9479bc3383bb270bd06abfa849`, with two order-balanced
HADES/PLAIN pairs, Hermes 0.21.6, Ollama 0.40.1, the same Qwen3.6 35B digest,
verified 65,536-token context, and the immutable network-disabled rootless
sandbox. Model warm/reset behavior and phase-specific sampling seeds were
matched by the benchmark runner.

## Result

The paired task medians were 63.91 seconds for HADES and 56.12 seconds for
PLAIN STACK. All four independent tests passed, all four commits stayed within
the expected source-only scope, and both HADES tasks committed successfully.
This is a two-pair synthetic result, not an owner preference or broad coding
quality result.

HADES' `review_diff` stage spent a median 10.17 seconds before the original
Hermes run method began; the original method then took a median 3.58 seconds.
The helper-level measurements identify
`tools.working_diff.collect_working_diff` as the pre-call cost. Its Git
subprocess breakdown was:

| Operation | Median elapsed |
|---|---:|
| `git rev-parse` | 8.55 s |
| two `git diff` calls | 1.05 s combined |
| `git ls-files` | 0.51 s |

The other timed workspace overlay helpers took under 12 ms each. A separate
staged-runtime probe measured Hermes' `selected_git_env()` at 7.89 seconds on
the first call and about 0.51 seconds on each of four warm calls. This strongly
implicates the package-manager Git environment lookup surrounding each Git
subprocess; the profile does not yet split that lookup from process startup
inside each timed command. No production behavior was changed.

## Decision

Treat this as a confirmed diff-review latency tax with a likely upstream
Hermes/package-manager cause. Keep the authenticated, bounded, read-only diff
evidence and current authority boundary. Next, isolate `selected_git_env()`
and Git process startup inside the staged Hermes runtime, then test the
smallest safe way to avoid repeating environment resolution across the
collector's related Git commands. Re-run the paired workflow before accepting
any production change. Do not claim this profile establishes Scotty's
preference.

The benchmark runner records only static helper/command names, counts, and
elapsed milliseconds for this instrumentation; it does not record helper
arguments, paths, prompts, or returned diff content.
