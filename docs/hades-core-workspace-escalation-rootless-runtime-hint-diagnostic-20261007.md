# Model-backed workspace escalation diagnostic (2026-10-07)

## Method

Ran one synthetic multi-file geometry task per stack with current Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B Q4_K_M model digest, 65,536 loaded context, reasoning disabled, and a real isolated rootless Docker 29.8.2 daemon. Sandbox containers had networking disabled and used the pinned immutable image. Both stack arms shared the model process and matched sampling seeds by task phase. The artifact stores timings, token counts, schema sizes, tool names, and test exit statuses only; it does not store prompts, file contents, or answers.

The first run used the existing HADES prompt. A second run tested one added HADES instruction clarifying that isolated terminal commands are available on an action follow-up, even when the preceding diagnosis was read-only. The candidate instruction was then reverted because it did not improve the observed action.

## Findings

- HADES used 2 schemas / 3,662 bytes in diagnosis and 5 / 9,575 bytes on the action turn. It kept diagnosis from changing the workspace and rejected a diagnosis-time terminal attempt as unavailable. After the explicit action follow-up, it patched the source but made no terminal test call. It accurately reported the patch as unverified.
- PLAIN exposed 8 schemas / 12,590 bytes in each phase. In the first repeat it patched and tested during diagnosis, before the action request. In the second repeat it waited for the action follow-up, patched, and called terminal tests.
- The independent post-run checks passed in all four workspace states: test exit 0, clean diff check, and only the expected geometry source changed. This confirms the final files, but does not count as HADES having run or verified the test during its action turn.
- Task latency was 39.41s PLAIN / 45.96s HADES in the first run, then 23.39s / 45.52s in the prompt-candidate run. These single samples are noisy and do not establish a causal latency change or owner preference. Both HADES runs exceeded the 30-second composed-task target.

The prompt hint did not cause an extra test call, so it was reverted. The remaining product defect is clear: after a successful code patch, HADES may end the action without running verification. Its existing response guard avoids falsely claiming a test passed, and diagnosis-time authority stayed bounded. The next work should target the tool-loop completion behavior while preserving those contracts.

This is synthetic diagnostic evidence only. It does not qualify broad coding quality, Git commit behavior, UI/gateway continuity, or Scotty preference. See `benchmarks/hades-core-workspace-escalation-rootless-runtime-hint-diagnostic-v1.json` for response-text-free measurements.
