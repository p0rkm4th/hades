# Current-turn workspace verification diagnostic (2026-10-07)

## Change

Workspace completion checks now require the upstream Hermes result boundary to match the active request's turn ID and exact user message, as well as point to a user row. A missing, malformed, stale, or mismatched boundary fails closed. Historical tool/test evidence cannot validate the active code change. When a boundary cannot be proven, HADES preserves existing transcript rows and appends its bounded response. When a code-verification notice is needed, it only replaces an assistant response inside the proven current-turn suffix; otherwise it appends the notice.

This follows Hermes 0.21.5's `agent.turn_context.export_current_turn_boundary`, which stamps `turn_id` and `current_turn_user_idx` only when the index is proven against the final result message projection and current user content. The extra HADES checks reject inconsistent metadata at the consumer boundary.

## Verification

- `scripts/test-workspace-escalation-hermes-runtime.sh` passed against an actual rootless Docker 29.8.2 daemon and the pinned network-disabled workspace image. Assertions cover stale prior test/tool results, missing/boolean/wrong-valid index, stale turn ID, successful fresh test evidence, owner isolation, workspace mount scope, and network isolation.
- `python3 -m py_compile hermes/sitecustomize.py hermes/workspace.py` passed.
- `git diff --check` passed.
- A fresh paired real-model escalation sample independently passed the fixture test and diff check in both PLAIN and HADES. HADES took 48.5 seconds versus PLAIN at 35.7 seconds, while using 7 versus 10 model generations. It is one synthetic sample, so it does not establish preference or a general latency result; HADES missed the 30-second composed-task target in this sample.

The public metrics artifact contains only control versions, timing/count measurements, and independent verification statuses. It contains no prompts, responses, transcripts, file contents, tool arguments, or local paths.

## Limits

This is a focused regression repair and synthetic diagnostic. It does not qualify the full owner corpus, natural owner preference, Git commit behavior, deployed Open WebUI continuity, or broad coding quality. The action prompt's instruction to run terminal verification remains guidance rather than a guarantee; the response guard still reports unverified work truthfully when fresh successful evidence is absent.
