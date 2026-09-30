#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: scripts/open-agent-zero-operator.sh SSH_TARGET [LOCAL_PORT]

Forward the optional HADES Agent Zero Operator gateway over an existing SSH
profile. The HADES gateway must already be enabled by an authorized operator.
The local listener binds to 127.0.0.1 only; this script never publishes it to
the LAN. Press Ctrl-C to close the tunnel.

Example:
  scripts/open-agent-zero-operator.sh codex@hades-core
  scripts/open-agent-zero-operator.sh hades-ssh 17004
EOF
}

target=${1:-}
local_port=${2:-7004}
if [[ -z "$target" || "$target" == -* ]]; then
  usage
  exit 2
fi
if [[ ! "$local_port" =~ ^[0-9]{1,5}$ ]] || ((10#$local_port < 1024 || 10#$local_port > 65535)); then
  echo 'FAIL local port must be an unprivileged TCP port from 1024 through 65535' >&2
  exit 2
fi
command -v ssh >/dev/null 2>&1 || { echo 'FAIL ssh is not installed' >&2; exit 127; }

printf 'Forwarding 127.0.0.1:%s to the HADES Operator gateway through %s.\n' "$local_port" "$target"
printf 'Open http://127.0.0.1:%s/ while this process is running; press Ctrl-C to disconnect.\n' "$local_port"
exec ssh \
  -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L "127.0.0.1:${local_port}:127.0.0.1:7004" \
  -- "$target"
