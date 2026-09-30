#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-operator-tunnel.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
mkdir -m 700 "$work/bin"
cat >"$work/bin/ssh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$HADES_TEST_SSH_ARGS"
exit "${HADES_TEST_SSH_EXIT:-0}"
EOF
chmod 700 "$work/bin/ssh"
export HADES_TEST_SSH_ARGS="$work/ssh-args"

PATH="$work/bin:$PATH" "$repo_dir/scripts/open-agent-zero-operator.sh" hades-test 17004
grep -Fx -- '-N' "$HADES_TEST_SSH_ARGS" >/dev/null
grep -Fx -- 'ExitOnForwardFailure=yes' "$HADES_TEST_SSH_ARGS" >/dev/null
grep -Fx -- 'ServerAliveInterval=30' "$HADES_TEST_SSH_ARGS" >/dev/null
grep -Fx -- 'ServerAliveCountMax=3' "$HADES_TEST_SSH_ARGS" >/dev/null
grep -Fx -- '127.0.0.1:17004:127.0.0.1:7004' "$HADES_TEST_SSH_ARGS" >/dev/null
[[ $(tail -n 1 "$HADES_TEST_SSH_ARGS") == hades-test ]]

if PATH="$work/bin:$PATH" "$repo_dir/scripts/open-agent-zero-operator.sh" hades-test 22 >/dev/null 2>&1; then
  echo 'FAIL privileged local ports must be rejected' >&2
  exit 1
fi
if PATH="$work/bin:$PATH" "$repo_dir/scripts/open-agent-zero-operator.sh" >/dev/null 2>&1; then
  echo 'FAIL missing SSH target must be rejected' >&2
  exit 1
fi
echo 'PASS Agent Zero Operator tunnel binds loopback only and validates the SSH target and local port'
