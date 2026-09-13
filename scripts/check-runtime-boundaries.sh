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
require_binding hades-hindsight 9999 '127.0.0.1:9999'

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
