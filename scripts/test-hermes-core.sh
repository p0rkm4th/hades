#!/usr/bin/env bash
set -euo pipefail

# Run the expanded HADES-relevant Hermes candidate contract with the
# candidate's own hermetic interpreter. This is qualification evidence, not
# a full upstream-suite result. The one excluded test is an upstream SQLite
# connection-tracing assertion documented in docs/hermes-staging-evaluation.md.

CANDIDATE=${1:-}
HINDSIGHT_PLUGIN_DIR=${2:-}
if [[ -z "$CANDIDATE" || ! -d "$CANDIDATE" ]]; then
  printf 'usage: %s HERMES_CANDIDATE_DIRECTORY [HINDSIGHT_PLUGIN_DIRECTORY]\n' "$0" >&2
  exit 2
fi

PYTHON="$CANDIDATE/.venv/bin/python"
[[ -x "$PYTHON" ]] || { printf 'FAIL candidate interpreter missing\n' >&2; exit 1; }
"$PYTHON" -c 'import pytest' >/dev/null 2>&1 || {
  printf 'FAIL candidate environment missing pytest\n' >&2
  exit 1
}

# The Hindsight provider tests exercise both the client API and embedded
# provider paths. Fail before collection if a disposable candidate was
# partially provisioned; otherwise the suite reports misleading behavior
# failures (and background-thread errors) for a missing dependency.
"$PYTHON" -c 'import hindsight_client_api' >/dev/null 2>&1 || {
  printf "FAIL candidate environment missing hindsight-client==0.6.1 (use a fresh/disposable venv)\n" >&2
  exit 1
}

RUNNER="$CANDIDATE/scripts/run_tests.sh"
[[ -x "$RUNNER" ]] || { printf 'FAIL candidate canonical test runner missing\n' >&2; exit 1; }

candidate_clean() {
  git -C "$CANDIDATE" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    printf 'FAIL candidate is not a Git checkout\n' >&2
    return 1
  }
  [[ -z "$(git -C "$CANDIDATE" status --porcelain --untracked-files=all)" ]] || {
    printf 'FAIL candidate checkout is dirty; use a fresh disposable checkout\n' >&2
    return 1
  }
}

candidate_clean || exit 1

tests=(
  tests/agent/test_memory_provider.py
  tests/agent/test_memory_provider_unavailable_warning.py
  tests/agent/test_declared_conversation_scope.py
  tests/acp_adapter/test_acp_mcp_discovery.py
  tests/agent/transports/test_hermes_tools_mcp_server.py
  tests/gateway/relay/test_auth.py
  tests/gateway/relay/test_identity_token_resolver.py
)

if [[ -f "$CANDIDATE/tests/test_hermes_state.py" ]]; then
  tests+=(tests/test_hermes_state.py)
elif [[ -f "$CANDIDATE/tests/hermes_state/test_hermes_state.py" ]]; then
  tests+=(tests/hermes_state/test_hermes_state.py)
else
  printf 'FAIL candidate Hermes state test missing\n' >&2
  exit 1
fi

bundled_hindsight_test="$CANDIDATE/tests/plugins/memory/test_hindsight_provider.py"
if [[ -f "$bundled_hindsight_test" ]]; then
  tests+=(tests/plugins/memory/test_hindsight_provider.py)
elif [[ -n "$HINDSIGHT_PLUGIN_DIR" && -f "$HINDSIGHT_PLUGIN_DIR/tests/test_provider.py" ]]; then
  : # Current Hermes releases ship the provider as a catalog plugin.
else
  printf 'FAIL candidate Hindsight provider test missing; pass its pinned catalog plugin directory\n' >&2
  exit 1
fi

for test in "${tests[@]}"; do
  [[ -f "$CANDIDATE/$test" ]] || {
    printf 'FAIL missing candidate test: %s\n' "$test" >&2
    exit 1
  }
done

cd "$CANDIDATE"
set +e
"$RUNNER" "${tests[@]}" \
  -k 'not test_search_projection_skips_context_enrichment_queries' \
  -q --disable-warnings --file-retries 0
status=$?
set -e
if (( status == 0 )) && [[ ! -f "$bundled_hindsight_test" ]]; then
  "$PYTHON" -m pytest "$HINDSIGHT_PLUGIN_DIR/tests" -q --disable-warnings
  status=$?
fi
if ! candidate_clean; then
  printf 'FAIL candidate checkout changed during qualification\n' >&2
  exit 1
fi
exit "$status"
