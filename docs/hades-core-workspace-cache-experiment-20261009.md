# Workspace review cache experiment — 2026-10-09

## Question

Can moving native Git diff evidence out of HADES' per-turn system prompt restore
prefix-cache reuse for the read-only review turn?

## Candidate and method

The candidate was based on source commit
`6d7d49e0a16c6a6c5119f4ad6c4e1e3273655e7d`; its uncommitted overlay/test patch
SHA-256 was
`b33ae10dc9234705a5ce441a2a0a3b632b3c4d141245024ebf9caea46b8715ea`. It moved
bounded diff evidence to Hermes 0.21.6's API-only user prefill and used one
shared workspace instruction across diagnosis, action, and review turns. The
candidate also combined the former task-specific instructions, making the
system prompt larger.

Two order-balanced PLAIN/HADES pairs used Hermes 0.21.6, Ollama 0.40.1,
Qwen3.6:35b Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536 context, and the same rootless Docker 29.8.2 VFS daemon and pinned
network-disabled workspace image. Each arm unloaded and identically rewarmed
the model. Independent test, diff, commit-scope, and clean-worktree checks
passed for all four tasks. The candidate itself passed the focused runtime
contract against the actual rootless daemon, including household denial and
distinct subject mounts.

## Result

| Measure | PLAIN | HADES candidate |
|---|---:|---:|
| Median task time | 52.88 s | 66.43 s |
| Median model calls per task | 11.5 | 12.0 |
| Median tool results per task | 6.5 | 7.5 |
| Focused-test terminal calls across two tasks | 4 | 2 |
| Local commits and independent checks | 2/2 | 2/2 |
| Review request cached tokens | n/a | 0 in both repeats |
| Review request first event | n/a | 8.27 s median |
| Review request elapsed | n/a | 9.81 s median |

HADES remained 13.55 seconds slower at the median (25.6%). The earlier
concise-review replay measured a 13.84-second gap (26.8%), so this difference
does not show a meaningful task-level improvement. Review requests still had
no cached tokens; first-event latency and request latency were slightly worse
than the prior candidate sample. The shared system prompt measured 14,878
bytes, versus 13,523 bytes in the prior review requests. The test confirms the
candidate placed evidence in a user-role prefill; its captured request had 908
user-role bytes. Provider bodies were not retained. The earlier telemetry
marker searched the system role only, so its `workspace_diff_evidence_present`
false value cannot establish whether the marker was present in that user
prefill.

## Interpretation and decision

Reject the implementation candidate. It added prompt text, did not restore
cache hits, and did not materially reduce the measured HADES tax. No candidate
behavior change was retained.

Hermes 0.21.6 source explains why the initial cache theory was incomplete:
`agent/conversation_loop.py` says tool schemas are serialized ahead of the
system prompt, while this HADES review request intentionally exposes zero tool
schemas. Hermes places prefill messages after the system prompt in
`agent/turn_request_assembly.py`. This makes tool-surface variation a plausible
cache-prefix break even when the system text is stable. The benchmark did not
isolate that cause, so treat it as a hypothesis for a small request-order
experiment, not a proven attribution.

The benchmark telemetry now scans all API message roles when recording whether
diff evidence was present. It stores only booleans and does not retain prompt,
diff, response, tool-argument, or tool-result text.

## Limits and artifact

This is a two-pair synthetic coding workflow. It does not qualify broad coding
usability, Open WebUI/deployed behavior, answer quality, or Scotty preference.
The sanitized provider telemetry is in
[`hades-core-owner-workspace-cache-candidate-20261009.json`](../benchmarks/hades-core-owner-workspace-cache-candidate-20261009.json).
