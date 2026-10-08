# Workspace provider prefix continuity check (2026-10-07)

## Question

Which provider request components diverge between HADES' last read-only
diagnosis call and the first authorized action call, and does keeping the system
instruction and read schemas stable restore Ollama prompt-cache reuse?

## Method

The workspace benchmark now records common-prefix byte lengths for serialized
system messages, conversation messages, and tool schemas. It keeps those bytes
only in the running benchmark process; the artifact contains lengths,
equality flags, and counts only. Four synthetic pairs were run in two cells,
each with two order-balanced repeats, using the pinned Hermes 0.21.5 / Ollama
0.40.0 / Qwen3.6 35B stack, verified 65,536 context, and the same rootless,
network-disabled container image.

The baseline kept HADES' existing phase-specific prompt and dynamic catalog.
The candidate combined a shared workspace instruction with read-only tools at
the start of the later action catalog. HADES still exposed only two read tools
during diagnosis; action tools remained absent until the explicit follow-up.
The candidate is a diagnostic experiment; its code changes were reverted after
the run.

## Findings

- In the baseline HADES requests, the diagnosis and action system messages were
  not identical. Their serialized common prefix was about 12.7 KB; the action
  system message was 13.7 KB. The transcript's common serialized prefix also
  stopped at about 12.7 KB, at the end of that changed system message.
- The baseline diagnosis and action tool catalogs shared only 29 serialized
  bytes in their existing upstream order. The action call reported zero cached
  prompt tokens in both HADES repeats. PLAIN reused 7,494 and 7,749 tokens on
  those two action calls.
- The combined candidate made the system message identical across phases and
  extended the schema prefix to 3,664 bytes, covering the two read schemas.
  HADES still reported zero cached prompt tokens in both action calls. This
  means the simple prompt-text and schema-order changes do not explain or fix
  the cache miss by themselves.
- The candidate produced no model-observed test evidence in either HADES action
  turn. Independent final tests passed in all four workspaces, but those tests
  cannot stand in for assistant verification. The candidate therefore adds no
  demonstrated usability value and was rejected.

The byte-prefix measurements are a clue about the OpenAI-compatible request
serialization, not proof of how Ollama tokenizes or stores its KV cache. The
underlying cache behavior remains unresolved. No product behavior change is
retained from this experiment.

## Next action

Keep the current per-turn capability boundary and test-reporting guard. Inspect
the upstream Hermes and Ollama request construction around tool schemas and
multi-turn context, then test a provider-supported cache strategy only if it
preserves the diagnosis/action authority split. Do not infer a cache fix from
byte-prefix overlap alone.

Artifact: [sanitized prefix-continuity measurements](../benchmarks/hades-core-workspace-prefix-continuity-v1.json).
