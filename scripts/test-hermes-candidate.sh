#!/usr/bin/env bash
set -euo pipefail

# Run promotion-critical Hermes candidate tests with the candidate's own
# interpreter. Disposable clones can retain a pytest launcher pointing at a
# different checkout.

CANDIDATE=${1:-}
if [[ -z "$CANDIDATE" || ! -d "$CANDIDATE" ]]; then
  printf 'usage: %s HERMES_CANDIDATE_DIRECTORY\n' "$0" >&2
  exit 2
fi

PYTHON="$CANDIDATE/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  printf 'FAIL candidate interpreter missing\n' >&2
  exit 1
fi

tests=(
  tests/agent/test_memory_provider.py
  tests/agent/test_memory_provider_unavailable_warning.py
  tests/agent/test_declared_conversation_scope.py
  tests/acp_adapter/test_acp_mcp_discovery.py
  tests/agent/transports/test_hermes_tools_mcp_server.py
  tests/gateway/relay/test_auth.py
  tests/gateway/relay/test_identity_token_resolver.py
)

for test in "${tests[@]}"; do
  [[ -f "$CANDIDATE/$test" ]] || { printf 'FAIL missing candidate test: %s\n' "$test"; exit 1; }
done

cd "$CANDIDATE"
exec "$PYTHON" -m pytest -q --disable-warnings "${tests[@]}"
