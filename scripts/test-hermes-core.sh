#!/usr/bin/env bash
set -euo pipefail

# Run the expanded HADES-relevant Hermes candidate contract with the
# candidate's own hermetic interpreter. This is qualification evidence, not
# a full upstream-suite result. The one excluded test is an upstream SQLite
# connection-tracing assertion documented in docs/hermes-staging-evaluation.md.

CANDIDATE=${1:-}
if [[ -z "$CANDIDATE" || ! -d "$CANDIDATE" ]]; then
  printf 'usage: %s HERMES_CANDIDATE_DIRECTORY\n' "$0" >&2
  exit 2
fi

PYTHON="$CANDIDATE/.venv/bin/python"
[[ -x "$PYTHON" ]] || { printf 'FAIL candidate interpreter missing\n' >&2; exit 1; }
"$PYTHON" -c 'import pytest' >/dev/null 2>&1 || {
  printf 'FAIL candidate environment missing pytest\n' >&2
  exit 1
}

RUNNER="$CANDIDATE/scripts/run_tests.sh"
[[ -x "$RUNNER" ]] || { printf 'FAIL candidate canonical test runner missing\n' >&2; exit 1; }

tests=(
  tests/agent/test_memory_provider.py
  tests/agent/test_memory_provider_unavailable_warning.py
  tests/agent/test_declared_conversation_scope.py
  tests/acp_adapter/test_acp_mcp_discovery.py
  tests/agent/transports/test_hermes_tools_mcp_server.py
  tests/gateway/relay/test_auth.py
  tests/gateway/relay/test_identity_token_resolver.py
  tests/plugins/memory/test_hindsight_provider.py
  tests/test_hermes_state.py
)

for test in "${tests[@]}"; do
  [[ -f "$CANDIDATE/$test" ]] || {
    printf 'FAIL missing candidate test: %s\n' "$test" >&2
    exit 1
  }
done

cd "$CANDIDATE"
exec "$RUNNER" "${tests[@]}" \
  -k 'not test_search_projection_skips_context_enrichment_queries' \
  -q --disable-warnings --file-retries 0
