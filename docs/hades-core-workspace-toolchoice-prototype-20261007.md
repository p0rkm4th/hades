# Workspace verification: native tool-choice prototype

## Result

The benchmark-only intervention did not reliably make Hermes run a fresh test after an action-turn code change. It produced a named `terminal` tool call in one of two HADES runs. The unmodified HADES baseline had also produced an action-phase test call in one of two earlier matched repeats. This experiment therefore shows no improvement and is excluded from completion and preference scoring.

In both prototype runs, the proxy captured a streamed HTTP 200 response to the named-choice request. In repeat 0 the response ended with `finish_reason=stop` and contained no tool call. In repeat 1 it ended with `finish_reason=tool_calls` and returned `terminal`. The model/runtime honored the requested choice once and did not honor it once in this sample. This is evidence that the mechanism is not dependable for this setup, not evidence of a protocol violation.

All four final workspaces (two per stack) passed independent tests and diff checks, with only the expected source file changed. That verifies the resulting files, not assistant verification during the conversation. Both prototype HADES diagnosis phases remained read-only. One prototype HADES action phase changed the source but produced no test call; the existing guard correctly reported the result as unverified.

## Method

Two order-balanced synthetic diagnosis → action comparisons used Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B model digest, a measured 65,536-token context, and the same isolated rootless Docker daemon and immutable no-network sandbox image. The HADES arm loaded its current overlay. The prototype temporarily set Hermes `request_overrides.tool_choice` to the named native `terminal` tool after a successful workspace code mutation and restored the previous overrides after the ensuing terminal round.

Across these two paired repeats, median task time was 42.35s for PLAIN and 41.90s for HADES with the prototype; median model generations were 10 and 6.5, and median tool results were 14.5 and 7.5, respectively. These tiny-sample observations do not establish a latency benefit or owner preference. Both stacks exceeded the 30s composed-task target in at least one run. The response-free measurements are in [`hades-core-workspace-toolchoice-prototype-hermes0215-ollama040-v1.json`](../benchmarks/hades-core-workspace-toolchoice-prototype-hermes0215-ollama040-v1.json).

Prompts, generated responses, tool arguments, and file contents are excluded from the public artifact. The raw local capture is private and must not be published.

## Decision

Do not promote this monkey-patch prototype into production. It adds benchmark-specific interception without demonstrating improved action completion. Keep the current truthful unverified guard and diagnosis-time mutation boundary. Continue examining Hermes' native tool loop and supported continuation/completion behavior for a minimal, repeatable post-mutation verification path. Re-run a larger paired sample before drawing product conclusions.
