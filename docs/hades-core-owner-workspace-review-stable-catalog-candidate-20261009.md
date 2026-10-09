# Stable workspace catalog during read-only diff review — 2026-10-09

## Candidate

The review turn now retains the same five workspace tool schemas sent on the
preceding coding turns so Ollama can reuse their cached prefix. The request
sets `tool_choice` to `none`, and HADES sets `valid_tool_names` to an empty set.
Schemas remain visible to the model; no tool is authorized to execute during
review.

The candidate is based on `59d644801dcb4f76868322ac99223739cccf0f87`; its
working-tree patch SHA-256 was
`bb9dc2c38a3dc5a4c387ef9361d445d56669bf0288f151012f2bcddd5bc0d334`.

## Matched replay

Two order-balanced PLAIN/HADES five-turn workflow pairs used Hermes 0.21.6,
Ollama 0.40.1, Qwen3.6:35b Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536 context, and the same rootless Docker 29.8.2 VFS daemon and pinned
network-disabled sandbox. Each arm unloaded and identically rewarmed the
model. All four tasks passed independent tests, diff checks, intended-file
scope checks, and clean-commit checks.

| Measure | PLAIN | HADES candidate |
|---|---:|---:|
| Median whole-task time | 51.00 s | 59.92 s |
| Median model calls | 12.5 | 10.5 |
| Median tool results | 7.5 | 6.0 |
| Successful tested, source-only commits | 2/2 | 2/2 |
| Review-turn tool results | 1 total | 0 total |

Both HADES review requests included five schemas, but had `tool_choice=none`,
an empty executable allowlist, and zero tool-call deltas. They reused 5,225/5,885
and 5,223/5,924 prompt tokens. Median first-event latency was 1.995 s and
request latency was 3.43 s. The prior zero-schema candidate had no cached
tokens, median first-event latency 8.27 s, and request latency 9.81 s.
The measured HADES whole-task median fell by 6.51 s from 66.43 s to 59.92 s;
HADES remains 8.92 s slower than PLAIN in this sample.

## Authorization and limits

The focused Hermes runtime contract passed against the real rootless daemon.
It checks the retained five schemas, empty `valid_tool_names`, and
`tool_choice=none`; it also feeds a synthetic `terminal` call to Hermes'
validator and confirms the call is rejected before execution. The matched
replay itself produced no review-turn tool calls in 2/2 HADES runs.

This is a promising latency tradeoff, not usability qualification. Five schemas
are visible to the model during review even though the turn cannot use them.
The sample is small, does not include adversarial diff text in the model replay,
and has no owner answer-quality or preference labels. Keep it as a candidate
for direct dogfood and targeted adversarial review; do not treat these results
as proof that HADES is preferred.

Sanitized metrics: [paired replay artifact](../benchmarks/hades-core-owner-workspace-review-stable-catalog-candidate-20261009.json).
