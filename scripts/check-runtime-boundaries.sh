#!/usr/bin/env bash
set -euo pipefail

# Verify the production exposure boundary without inspecting credentials or
# application data. Open WebUI is intentionally LAN-reachable; its backends
# remain loopback-only.

require_binding() {
  local container=$1 port=$2 expected=$3 actual
  actual=$(docker port "$container" "$port/tcp" 2>/dev/null || true)
  [[ -n "$actual" ]] || { printf 'FAIL %s port %s is not published\n' "$container" "$port"; exit 1; }
  case "$actual" in
    "$expected"*) printf 'PASS %s %s -> %s\n' "$container" "$port" "$actual" ;;
    *) printf 'FAIL %s %s unexpected binding: %s\n' "$container" "$port" "$actual"; exit 1 ;;
  esac
}

require_binding hades-open-webui 8080 '0.0.0.0:3000'
require_binding hades-lldap-production 17170 '127.0.0.1:17171'
require_binding hades-grocy 80 '127.0.0.1:7003'
require_binding hades-agent-zero 80 '127.0.0.1:7002'
require_binding hades-searxng 8080 '127.0.0.1:8080'
require_binding hades-hindsight 8888 '127.0.0.1:8888'

if docker ps --format '{{.Ports}}' | grep -Eq '(^|[^0-9])7001([^0-9]|$)'; then
  printf 'FAIL obsolete 7001 exposure detected\n'
  exit 1
fi
printf 'PASS no obsolete 7001 exposure\n'
