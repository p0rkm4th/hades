# Concise native diff review candidate — 2026-10-08

## Change

The owner-only, read-only native diff review instruction now asks for a concise
summary naming changed files, the main change, and whether unrelated changes
appear in the complete diff. Existing instructions still require authenticated
read-only diff evidence, untrusted-file handling, and an honest unavailable or
truncated-evidence response.

## Matched comparison

A two-repeat order-balanced five-turn synthetic `workflow-to-commit` run used
the same Hermes 0.21.6, Ollama 0.40.1, Qwen3.6:35b digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536 context, rootless Docker 29.8.2, VFS driver, pinned sandbox digest, and
multifile `error_message` fixture as the preceding matched replay. The HADES
change ran from source `fdc8fb6026fdebf13ba25dfcaf91ad3cdf55dcdd`. Each arm
unloaded and identically rewarmed the model before measurement.

All four independent test, diff-check, source-only change, commit, and
clean-worktree checks passed. The telemetry contains no prompts, responses,
commands, or tool-result text.

| Measure | Previous HADES prompt | Concise-review HADES |
|---|---:|---:|
| Median task time | 64.35 s | 65.44 s |
| Median diff-review phase | 19.62 s | 18.77 s |
| Review response completion tokens | 131 median | 64.5 median |
| Review response latency | 10.10 s median | 8.79 s median |
| Review first-event latency | 7.38 s median | 7.37 s median |
| Model calls per task | 11.0 median | 11.5 median |
| Tool results per task | 8.0 median | 7.5 median |
| Tasks independently verified | 2/2 | 2/2 |

The response used roughly half as many completion tokens and took about 1.3
seconds less per review request in this sample. First-event latency did not
change. The whole-task median was 1.10 seconds higher in this run, reflecting
noise across the small sample; the task-level difference versus PLAIN was
13.84 seconds (26.8%) here, compared with 15.64 seconds (32.1%) in the prior
run. The diff-review stage remains the largest measured HADES tax.

The concise instruction is a small response-style improvement, not a net
usability qualification or evidence that Scotty prefers HADES. Keep it while
profiling the high review first-event latency and remaining HADES/PLAIN task
gap. Answer quality and naturalness still require owner review.

Sanitized telemetry: [`hades-core-owner-workspace-concise-review-candidate-20261008.json`](../benchmarks/hades-core-owner-workspace-concise-review-candidate-20261008.json).
