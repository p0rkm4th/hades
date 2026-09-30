#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/workspace"
printf 'synthetic-secret-never-print\n' > "$tmp/workspace/.env"
chmod 644 "$tmp/workspace/.env"
cat > "$tmp/bin/docker" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
root=${HADES_TEST_AGENT_ZERO_ROOT:?}
if [[ "$1" == exec && "$2" == hades-agent-zero && "$3" == test && "$4" == -f && "$5" == /a0/usr/.env ]]; then
  test -f "$root/.env"
elif [[ "$1" == exec && "$2" == --user && "$3" == 0 && "$4" == hades-agent-zero && "$5" == chmod && "$6" == 600 && "$7" == /a0/usr/.env ]]; then
  chmod 600 "$root/.env"
elif [[ "$1" == exec && "$2" == --user && "$3" == 0 && "$4" == hades-agent-zero && "$5" == stat && "$6" == -c && "$7" == %a && "$8" == /a0/usr/.env ]]; then
  stat -c %a "$root/.env"
else
  echo 'unexpected docker invocation' >&2
  exit 90
fi
SH
chmod 700 "$tmp/bin/docker"
output=$(PATH="$tmp/bin:$PATH" HADES_TEST_AGENT_ZERO_ROOT="$tmp/workspace" HADES_AGENT_ZERO_WORKSPACE_WAIT_SECONDS=0 bash "$repo_dir/scripts/secure-agent-zero-workspace.sh")
[[ "$(stat -c %a "$tmp/workspace/.env")" == 600 ]]
[[ "$output" == 'PASS Agent Zero private workspace environment file is mode 0600' ]]
! grep -q 'synthetic-secret-never-print' <<<"$output"
echo 'PASS Agent Zero workspace secret permissions are repaired without disclosure'
