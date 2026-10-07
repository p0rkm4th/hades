# Hermes verify-on-stop with isolated workspaces

## Result

The paired diagnostic confirms a path-mapping gap in the isolated Docker workspace setup. Native `verify_on_stop` was enabled in both PLAIN and HADES, and each arm recorded one changed code path. Hermes saw each changed path under the container's `/workspace` mount, where host-side project discovery returned no project facts. The corresponding host workspace was a recognized project, but its evidence ledger remained `unverified`. Neither arm produced a native stop nudge.

The model/runtime did run a follow-up tool round, and independent tests passed for both final workspaces. Those facts do not show that the native verification ledger recognized the test. The terminal evidence result was absent, consistent with Hermes evaluating the container working directory outside the host-visible project root.

This is a confirmed integration gap for this benchmark's Docker workspace mapping. It is not yet proof that every deployed HADES workspace backend has the same path behavior. Hermes' stop gate walks changed paths and asks the host process to discover a project root from each path; the isolated terminal reports `/workspace` paths, while HADES' real project lives at a host workspace path. A fix needs to preserve subject isolation and align both edit invalidation and test evidence on the same canonical host workspace and session identity.

## Method and measurements

One synthetic diagnosis → coding-action pair used the same Hermes 0.21.5 source, Ollama 0.40.0 process, Qwen3.6 35B model digest, measured 65,536-token context, rootless Docker 29.8.2/VFS daemon, and immutable no-network task image. `HERMES_VERIFY_ON_STOP=1` was inherited by both arms. Diagnosis remained read-only in both, and independent tests, diff checks, and expected-source-only checks passed in both.

The pair took 29.6 seconds for PLAIN and 37.5 seconds for HADES, with 10 versus 7 model generations and 9 versus 8 tool results. With one task per arm these are descriptive diagnostics only, excluded from latency qualification and owner-preference scoring. The response-free data is in [`hades-core-native-verify-on-stop-workspace-mapping-v1.json`](../benchmarks/hades-core-native-verify-on-stop-workspace-mapping-v1.json).

Prompts, model responses, tool arguments, and file contents are excluded from the artifact. The raw local capture is private and must be deleted after this sanitized record is retained.

## Decision

Do not enable native verify-on-stop in production for the isolated Docker workspace flow yet. The gate cannot enforce its intended contract while changed paths and terminal evidence resolve outside the same recognized project root. The benchmark instrumentation now records only path categories and recognition/evidence states, not the paths themselves.

Next, trace the deployed HADES workspace adapter's edit path, terminal `cwd`, task/session ID, and Hermes session ID. Then test a minimal canonical-root mapping so edit invalidation and terminal evidence share the same recognized workspace and session. Retain the existing truthful unverified report and read-only diagnosis boundary until the mapped flow passes the full stale-after-edit → passing-test → no-nudge check and proves no nudge on unaffected turns.
