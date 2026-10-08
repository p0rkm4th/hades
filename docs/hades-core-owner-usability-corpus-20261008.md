# HADES Core owner usability corpus v1

Status: candidate for owner review; no owner preference labels are assigned.

This is a 54-case synthetic conversation corpus for comparing HADES with a
minimal supported Hermes/runtime control. It covers ordinary chat, follow-up
context, memory, household/Grocy, homelab reads, research, coding/workspace
escalation, bounded computer use, multi-user isolation, and tool failure or
recovery. Cases include terse turns, corrections, interruptions, topic
switches, cancellation, and continuation.

The cases were authored from themes in the sanitized
[`daily-driver-failures.md`](daily-driver-failures.md), existing domain and
authority contracts, and the recent synthetic workspace-escalation experiment.
They are not raw owner transcripts and do not constitute owner-approved task
wording. The `owner_preference` field intentionally remains `unrated` until
direct dogfood records preference and observed friction.

Each case names the capability surface expected, behavior that should occur,
and behavior that must not occur. This is a task specification, not yet a
replay runner or a quality score. The companion
[`test-hades-core-usability-corpus-contract.sh`](../scripts/test-hades-core-usability-corpus-contract.sh)
checks corpus shape, category coverage, uniqueness, and basic secret hygiene.

## Comparison protocol to apply

For HADES and PLAIN STACK, hold the model, quantization, context length,
sampling, runtime, hardware, prompt, network conditions, and warm/cold state
constant where practical. Record deviations. Capture latency, generations,
tools exposed and called, avoidable calls, context size, task completion,
verification, clarification/confirmation, failure behavior, response length,
agentic ceremony, and direct owner preference. Keep unsuccessful runs in the
results and report sample counts. Do not grade naturalness with keyword-only
rules. A case without an applicable capability should test that no unrelated
tool or domain system is activated.

The corpus is not evidence that HADES currently passes these tasks. A full
comparative run and direct Scotty dogfood remain required before drawing a
product-preference conclusion.
