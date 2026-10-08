# Workspace escalation with the accepted image pin (2026-10-07)

## Method

Ran four order-balanced synthetic multi-file diagnosis → explicit-fix pairs
through PLAIN and HADES. Both arms used Hermes 0.21.5, Ollama 0.40.0,
Qwen3.6 35B Q4_K_M (`a7eb95c5…`), and the same loaded 65,536-token context.
The candidate workspace image was pinned to
`docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d`.
Both arms ran in the same rootless Docker 29.8.2 daemon; each container had
networking disabled. The daemon's `RepoDigests` included the exact pin, and a
read-only, network-disabled image smoke test passed before the benchmark.

To acquire that image, the disposable rootless daemon briefly used
[slirp4netns 1.3.6](https://github.com/rootless-containers/slirp4netns/releases/tag/v1.3.6)
with host-loopback disabled. The official release's checksum file matched its
published SHA-256; the binary checksum matched that file. The daemon was
stopped and restarted with `--net=none` before the image smoke test and all
benchmark tasks. No system package or production service was changed.

The benchmark artifact contains aggregate counts and timings only. It excludes
prompts, assistant text, commands, file contents, tool arguments, transcripts,
local paths, and identity values.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median diagnosis → fix time | 41.1 s (39.0–43.0) | 49.2 s (46.9–55.1) |
| Median model generations | 8 | 8 |
| Median tool results | 11 | 9.5 |
| Diagnosis schemas / serialized bytes | 8 / 12,590 | 2 / 3,662 |
| Action schemas / serialized bytes | 8 / 12,590 | 5 / 9,575 |
| Median first model content in diagnosis | 13.1 s | 8.7 s |
| Diagnosis changed the project before “Fix it.” | 2/4 | 0/4 |
| Action turn returned test evidence | 2/4 | 4/4 |

Independent post-run tests and diff checks passed for all eight final workspaces,
with only the expected source change in each. These checks confirm the final
fixture states. They do not replace the assistant-run test evidence shown above.
The pairwise HADES time was 5.7–14.9 seconds longer in every repeat. Its
diagnosis TTFT and smaller catalog improved, but that did not translate into
faster task completion. PLAIN also changed the project during diagnosis in two
runs, before the explicit action follow-up; that is a task-sequencing and
authority failure despite the shorter elapsed time.

## Latency follow-up

The provider trace shows the same task cost more model time in HADES: median
time in model requests was 38.2 seconds versus 31.1 seconds for PLAIN, with
eight generations in both arms. PLAIN's action turn reused a median of about
7,400 prompt-cache tokens on its first model call; HADES reused none on that
call in all four pairs. HADES' serialized system messages differ between
diagnosis and action by 359 bytes, so the changed phase instructions looked
like a plausible cause.

Two isolated experiments did not prove or fix that cause. Putting the read
schemas first in both HADES catalogs left action cache hits at zero in two
pairs. Replacing the two phase-specific workspace instructions with one shared
instruction also left action cache hits at zero and did not improve latency in
two pairs. Both code experiments were reverted. The schema-order sample was
faster, but its two-pair sample is too small and it had no cache improvement;
that timing is not treated as a product result. The cache invalidation source
remains unresolved, so the overlay should not be changed based on this
hypothesis.

This is evidence that HADES' read-only diagnosis boundary and action-time test
behavior add value on this scenario. It is not a Scotty preference vote, and
the latency miss remains material. Four synthetic pairs are too small to
generalize to everyday coding work.

## Benchmark correction

An earlier attempt passed the rootless daemon a bare image config ID. HADES'
production pin validator correctly rejected it because it requires the
immutable `name@sha256:…` reference. That attempt produced no HADES workspace
schemas and is invalid for comparison; it is not included in the artifact. The
corrected run above pulled and inspected the exact accepted digest in the
isolated daemon before testing.

## Next action

Keep the diagnosis mutation boundary and truthful test reporting. Trace the
serialized provider context across the two HADES phases to find why the action
call misses a cache that PLAIN reuses, then repeat the task after a focused
change. Do not call this a general latency or owner-preference win.

Artifact: [sanitized four-pair measurements](../benchmarks/hades-core-workspace-escalation-valid-image-v1.json).
