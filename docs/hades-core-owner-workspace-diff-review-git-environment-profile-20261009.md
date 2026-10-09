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

The other timed workspace overlay helpers took under 12 ms each. The benchmark
uses a fresh `HOME`/`HERMES_HOME` for each arm, so the staged package manager
also initializes against a fresh tool store on each HADES run. A direct
`selected_git_env()` probe in that isolated build venv measured 7.89 seconds on
the first call and about 0.51 seconds on each of four warm calls. That cold
first-call cost is specific to the fresh-profile benchmark setup and should not
be projected onto a persistent owner profile.

To check the persistent-profile case, the same Hermes 0.21.6 candidate's
installed venv was run with its existing profile and a disposable Git repo
containing one tracked edit and one untracked file. `collect_working_diff()`
returned both changes successfully in 2.65 seconds on the first call and about
2.44 seconds on each of three warm calls. Thus the ~10.17-second synthetic
review setup is not the expected steady-state cost; the persistent-profile
collector still carries roughly 2.4 seconds of setup cost. This is a focused
helper measurement, not a matched PLAIN STACK workflow or a production service
measurement.

With timing around the persistent-profile helper, five Git environment lookups
accounted for 2.64 seconds on the first collection and 2.42 seconds on the
next; the five Git subprocesses together took about 8 milliseconds per
collection. The package-manager environment lookup, rather than Git diff
computation, is therefore the recurring helper cost in this probe.

## HADES adapter and verification

`hermes/workspace.py` now resolves Hermes' Git environment once per diff
collection and exposes it to the upstream collector through a `ContextVar`
scoped to that synchronous call. Hermes still applies the same
`noninteractive_git_env` and hardened Git arguments for every subprocess. The
context resets in `finally`, so later calls resolve a fresh environment and
parallel request contexts do not share a cached value.

A disposable Git fixture with one tracked edit and one untracked file produced
identical collector results before and after the adapter, and its worktree
status stayed unchanged. Across three alternating measurements, the uncached
collector median was 2.42 seconds and the scoped adapter median was 0.49
seconds; environment-selector calls fell from five to one. The real rootless
Hermes workspace contract passed, including the authenticated owner boundary,
read-only diff, household denial, and distinct subject workspaces.

Retained behavior:

- **Behavior:** reuse one selected Git environment during an authenticated
  owner's read-only native diff collection.
- **Upstream gap:** Hermes 0.21.6 resolves the package-manager environment
  separately for each Git subprocess in `collect_working_diff()`.
- **Proving evidence:** the disposable tracked/untracked collector replay and
  `scripts/test-workspace-escalation-hermes-runtime.sh` with the pinned,
  network-disabled rootless image.
- **Deletion trigger:** remove the adapter when Hermes accepts one selected
  environment for the whole collector operation, or otherwise avoids repeated
  environment resolution, and the same persistent-profile replay plus rootless
  workspace contract pass without the HADES adapter.

## Decision

The adapter removes most of the persistent-profile collector overhead in the
focused fixture. The subsequent [full paired rerun](hades-core-owner-workspace-env-cache-rerun-20261009.md)
passed both tasks in each stack and preserved completion behavior, though HADES
remained slower by median. That runner still initializes a fresh PM home per
arm. This profile does not establish Scotty's preference,
and no deployed service was changed.

The benchmark runner records only static helper/command names, counts, and
elapsed milliseconds for this instrumentation; it does not record helper
arguments, paths, prompts, or returned diff content.
