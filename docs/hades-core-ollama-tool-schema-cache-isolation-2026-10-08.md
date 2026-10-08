# Ollama tool-schema cache isolation probe (2026-10-08)

## Question

Can a tool-catalog change by itself explain why the HADES workspace action call
gets no prompt-cache reuse even when most serialized messages remain the same?

## Method

Sent direct OpenAI-compatible `/v1/chat/completions` requests to isolated
Ollama 0.40.0 and 0.40.1 runtimes, using the pinned Qwen3.6 35B Q4_K_M model,
one parallel slot, 65,536 context, fixed temperature and seed. The 0.40.1
Linux AMD64 archive was verified against the official SHA-256 in the artifact.
Each run used a large static system prefix (17,772 prompt tokens total) and
one `read_file` schema. The sequence repeated the exact request, appended one
`edit_file` schema without changing messages, repeated that request, then
changed only the user message while restoring the original schema.

Raw prompt text, schemas, and generated content were not retained. The model's
digest and only token counts are in the artifact.

## Result

- Exact repeat: 17,768 of 17,772 prompt tokens were reported as cached.
- Tool-only change: 0 of 17,841 tokens were reported as cached.
- Exact repeat of the changed-tool request: 17,837 of 17,841 tokens were cached.
- User-message-only change with the original tool list: 17,260 of 17,772 tokens were cached.
- Exact repeat of that changed-message request: 17,768 of 17,772 tokens were cached.

Ollama 0.40.1 produced the same six prompt and cache counts as Ollama 0.40.0.
The release notes contain no local inference or prompt-cache change; this
measured result agrees with that scope.

On both tested runtime versions with this model, changing tool schemas alone
removes reuse of the long shared prefix, while a changed user message retains
most of the cache. This supports the hypothesis that Ollama's Qwen prompt
rendering places tool schema material before the otherwise reusable message
prefix.

This was one direct-runtime diagnostic sequence per runtime version. It did
not replay a full Hermes diagnosis/action transcript and does not establish
behavior for other models or runtimes. It is causal evidence for tool-list
sensitivity in this configuration, not a product-performance or
owner-preference result. The next useful validation is the same schema-only
contrast against captured HADES provider requests, while keeping action
schemas unavailable during diagnosis.

Artifact: [sanitized token measurements](../benchmarks/hades-core-ollama-tool-schema-cache-isolation-v1.json).
