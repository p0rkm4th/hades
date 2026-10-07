# Hermes native verification path mapping prototype

## Result

Mapping Docker `/workspace` paths to the current host project made Hermes recognize edited code paths in the benchmark, and a focused synthetic ledger probe passed the root/session and containment checks. However, the model-backed result remains mixed. Across two order-balanced diagnosis → action pairs, only one of four tasks produced recognized native `passed` evidence. The four trials received four stop nudges in total; the sanitized artifact does not preserve enough per-task linkage to attribute those nudges to particular changed workspaces. One HADES task did not edit code and left the seeded test failing. Independent tests passed in three of the four final workspaces, which does not establish that Hermes recorded those tests during the turn.

The one-pair read-only control returned the expected answer in both stacks with no code mutations and zero stop nudges. This is a narrow no-edit control, not evidence that the gate stays quiet for every ordinary conversation.

The latest stable official Hermes release at the time of this run is v0.21.5, tagged v2026.9.24. The staged source matches that release. [Official Hermes release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.24)

## Method

Both stacks used Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B digest, measured 65,536-token context, rootless Docker 29.8.2/VFS, and the same immutable task image with task networking disabled. Native verify-on-stop was enabled identically in both arms. The benchmark-only prototype mapped only paths inside `/workspace` to the active synthetic workspace, checked resolved containment, and preserved the Hermes session ID.

Median task time was 99.5 seconds for PLAIN and 69.9 seconds for HADES; median model API calls were 29.5 and 19, and median tool results were 48 and 18.5. This small, highly variable sample is excluded from performance qualification and preference scoring. PLAIN changed workspace files during diagnosis in two tasks; HADES changed none during diagnosis and rejected one attempted mutation. The action fixture has no declared canonical verification recipe, which likely contributed to tests not being recognized by Hermes' ledger. The exact response-free measurements are in [`hades-core-native-verify-on-stop-workspace-mapping-prototype-v2.json`](../benchmarks/hades-core-native-verify-on-stop-workspace-mapping-prototype-v2.json).

The separate focused probe exercised a synthetic project with a canonical `make test` recipe. It confirmed that mapped edit and terminal paths share one host root, missing-or-stale evidence triggers a nudge, a passing terminal result clears the nudge, another session remains unverified, traversal is rejected, and a no-edit turn does not nudge. The sanitized artifact does not distinguish a missing-evidence case from a stale-evidence transition. The probe tests the benchmark helper and Hermes ledger directly; it does not prove a HADES production integration.

Prompts, responses, tool arguments, and fixture contents are excluded from the artifact. Raw captures are private and must be deleted after this sanitized result is retained.

## Decision

Do not enable native verify-on-stop in production or replace HADES' current same-turn truthful verification guard with it. The mapping itself can align the ledger keys, but the model-backed flow did not reliably produce commands accepted as fresh verification, and stop nudges added extra model rounds without establishing better task completion. Hermes defaults this feature off; this sample does not justify overriding that default.

Keep the smallest HADES same-turn evidence guard. If a future workspace upgrade supplies a canonical project test recipe and verified mount-root metadata to Hermes' terminal result finalizer, repeat a larger matched action sample before considering adoption. Preserve the diagnosis mutation boundary. The read-only control should be expanded to ordinary chat and follow-up turns in the full corpus.
