#!/usr/bin/env bash
set -euo pipefail

# Verify the production exposure boundary without inspecting credentials or
# application data. Open WebUI is intentionally LAN-reachable; its backends
# remain loopback-only.

require_binding() {
  local container=$1 port=$2 expected=$3 actual
  actual=$(docker port "$container" "$port/tcp" 2>/dev/null || true)
  [[ -n "$actual" ]] || { printf 'FAIL %s port %s is not published\n' "$container" "$port"; exit 1; }
  # Require the complete docker-port result. A prefix match would allow an
  # additional IPv6/public binding after the expected loopback line.
  if [[ "$actual" == "$expected" ]]; then
    printf 'PASS %s %s -> %s\n' "$container" "$port" "$actual"
  else
    printf 'FAIL %s %s unexpected binding: %s\n' "$container" "$port" "$actual"
    exit 1
  fi
}

require_binding hades-open-webui 8080 '0.0.0.0:3000'
require_binding hades-lldap-production 17170 '127.0.0.1:17171'
require_binding hades-grocy 80 '127.0.0.1:7003'
require_binding hades-agent-zero 80 '127.0.0.1:7002'
require_binding hades-searxng 8080 '127.0.0.1:8080'
require_binding hades-hindsight 8888 '127.0.0.1:8888'
require_binding hades-hindsight 9999 '127.0.0.1:9999'

agent_zero_card_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  'http://127.0.0.1:7002/a2a/.well-known/agent.json' 2>/dev/null || true)
if [[ "$agent_zero_card_status" == 401 ]]; then
  printf 'PASS Agent Zero native A2A agent card requires authentication\n'
else
  printf 'FAIL Agent Zero native A2A agent-card auth status: %s\n' "$agent_zero_card_status"
  exit 1
fi

hermes_host=$(docker exec hades-open-webui getent hosts host.docker.internal \
  2>/dev/null | awk 'NR == 1 { print $1 }' || true)
hermes_listener_count=$(ss -ltnH 2>/dev/null \
  | awk '$4 ~ /:8642$/ { count++ } END { print count + 0 }')
if [[ -n "$hermes_host" && "$hermes_listener_count" == 1 ]] && ss -ltnH 2>/dev/null \
  | awk '{print $4}' | grep -Fxq "${hermes_host}:8642"; then
  printf 'PASS Hermes bound only to the WebUI private host mapping\n'
else
  printf 'FAIL Hermes private host binding is missing or widened\n'
  exit 1
fi
hermes_unauth_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  "http://${hermes_host}:8642/v1/models" 2>/dev/null || true)
if [[ "$hermes_unauth_status" == 401 ]]; then
  printf 'PASS Hermes API rejects unauthenticated model access\n'
else
  printf 'FAIL Hermes API unauthenticated status: %s\n' "$hermes_unauth_status"
  exit 1
fi
hermes_cors_status=$(curl -sS -o /dev/null -w '%{http_code}' -X OPTIONS \
  -H 'Origin: https://untrusted.invalid' \
  -H 'Access-Control-Request-Method: GET' \
  "http://${hermes_host}:8642/v1/models" 2>/dev/null || true)
if [[ "$hermes_cors_status" == 403 ]]; then
  printf 'PASS Hermes rejects untrusted cross-origin requests\n'
else
  printf 'FAIL Hermes untrusted CORS status: %s\n' "$hermes_cors_status"
  exit 1
fi

if [[ -z "$(docker port hades-lldap-production 3890/tcp 2>/dev/null || true)" ]]; then
  printf 'PASS LLDAP LDAP listener is not host-published\n'
else
  printf 'FAIL LLDAP LDAP listener is host-published\n'
  exit 1
fi

if docker ps --format '{{.Ports}}' | grep -Eq '(^|[^0-9])7001([^0-9]|$)'; then
  printf 'FAIL obsolete 7001 exposure detected\n'
  exit 1
fi
printf 'PASS no obsolete 7001 exposure\n'

# A retired candidate provider once remained persisted in Open WebUI after
# its runtime was gone. Reject that known stale endpoint without prescribing
# which Hermes revision is currently active.
if docker exec hades-open-webui python3 -c 'import json,sqlite3,sys; c=sqlite3.connect("/app/backend/data/webui.db"); rows=c.execute("select value from config where key in (?,?)",("openai.api_base_urls","openai.api_configs")).fetchall(); sys.exit(1 if any("18645" in str(v) for (v,) in rows) else 0)' ; then
  printf 'PASS no retired 18645 provider configuration\n'
else
  printf 'FAIL retired 18645 provider configuration detected\n'
  exit 1
fi

if docker exec hades-open-webui python3 -c 'import sqlite3,sys; c=sqlite3.connect("/app/backend/data/webui.db"); row=c.execute("select value from config where key=?",("ui.enable_signup",)).fetchone(); sys.exit(0 if row and row[0] == "false" else 1)' ; then
  printf 'PASS unmanaged self-signup disabled\n'
else
  printf 'FAIL unmanaged self-signup is enabled\n'
  exit 1
fi

if docker exec hades-open-webui python3 -c 'import json,sqlite3,sys; c=sqlite3.connect("/app/backend/data/webui.db");
def value(key):
 row=c.execute("select value from config where key=?",(key,)).fetchone(); return row[0] if row else None
permissions=json.loads(value("user.permissions") or "{}")
sharing=permissions.get("sharing",{})
sys.exit(0 if value("auth.enable_api_keys") == "false" and sharing.get("public_chats") is False and sharing.get("open_chats") is False else 1)' ; then
  printf 'PASS API-key issuance and public chat sharing disabled\n'
else
  printf 'FAIL privileged API keys or public chat sharing enabled\n'
  exit 1
fi
