#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'find "$work" -depth -mindepth 1 -delete; rmdir "$work" 2>/dev/null || true' EXIT
mkdir -p "$work/bin" "$work/deployment"
cat > "$work/bin/docker" <<'MOCK'
#!/usr/bin/env bash
[[ "$1" == exec && "$2" == hades-agent-zero ]] || exit 7
printf '%s\n' "${MOCK_AGENT_ZERO_KEY:-0123456789abcdef}"
MOCK
chmod 700 "$work/bin/docker"
if ! PATH="$work/bin:$PATH" MOCK_AGENT_ZERO_KEY=0123456789abcdef \
  bash "$repo_dir/scripts/sync-agent-zero-client-auth.sh" "$work/deployment/client.env" > "$work/first.log"; then
  cat "$work/first.log" >&2
  exit 1
fi
test "$(stat -c '%a' "$work/deployment/client.env")" = 600
grep -qx 'AGENT_ZERO_API_KEY=0123456789abcdef' "$work/deployment/client.env"
! grep -q '0123456789abcdef' "$work/first.log"
before=$(stat -c '%i:%Y' "$work/deployment/client.env")
PATH="$work/bin:$PATH" MOCK_AGENT_ZERO_KEY=0123456789abcdef \
  bash "$repo_dir/scripts/sync-agent-zero-client-auth.sh" "$work/deployment/client.env" >/dev/null
test "$(stat -c '%i:%Y' "$work/deployment/client.env")" = "$before"
if PATH="$work/bin:$PATH" MOCK_AGENT_ZERO_KEY=short \
  bash "$repo_dir/scripts/sync-agent-zero-client-auth.sh" "$work/deployment/client.env" > "$work/bad.log" 2>&1; then
  echo 'FAIL sync accepted malformed Agent Zero token' >&2
  exit 1
fi
! grep -q '0123456789abcdef' "$work/bad.log"
grep -qx 'AGENT_ZERO_API_KEY=0123456789abcdef' "$work/deployment/client.env"
echo 'PASS Agent Zero client auth sync is protected, stable, and fail-safe'
