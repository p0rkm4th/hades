#!/usr/bin/env bash
set -Eeuo pipefail

destination=${1:-}
container=${2:-hades-agent-zero}
[[ "$destination" == /* ]] || { echo 'FAIL Agent Zero client-auth destination must be absolute' >&2; exit 2; }
[[ -d "$(dirname "$destination")" && ! -L "$(dirname "$destination")" ]] || {
  echo 'FAIL Agent Zero client-auth destination directory is missing or linked' >&2; exit 1;
}

# Ask the running pinned application for its own derived token. This avoids
# guessing how its persistent runtime ID was initialized and never prints it.
python_code='import sys,os,hashlib,base64; sys.path.insert(0, "/a0"); from helpers import dotenv; dotenv.load_dotenv(); rid=os.getenv("A0_PERSISTENT_RUNTIME_ID"); login=os.getenv("AUTH_LOGIN", ""); password=os.getenv("AUTH_PASSWORD", "");
if not rid: raise SystemExit("persistent runtime ID is missing");
print(base64.urlsafe_b64encode(hashlib.sha256(f"{rid}:{login}:{password}".encode()).digest()).decode().replace("=", "")[:16])'
api_key=$(docker exec "$container" /opt/venv-a0/bin/python -c "$python_code" 2>/dev/null) || {
  echo 'FAIL could not read Agent Zero API token from the running pinned service' >&2; exit 1;
}
[[ "$api_key" =~ ^[A-Za-z0-9_-]{16}$ ]] || {
  echo 'FAIL running Agent Zero returned an invalid API token shape' >&2; exit 1;
}

tmp=$(mktemp "$(dirname "$destination")/.agent-zero-client-auth.XXXXXX")
cleanup() {
  if [[ -n "${tmp:-}" && -e "$tmp" ]]; then find "$tmp" -delete; fi
}
trap cleanup EXIT
(umask 077; printf 'AGENT_ZERO_API_KEY=%s\n' "$api_key" > "$tmp")
chmod 600 "$tmp"
if [[ -f "$destination" ]] && cmp -s "$tmp" "$destination"; then
  find "$tmp" -delete
  tmp=''
else
  mv -f "$tmp" "$destination"
  tmp=''
fi
unset api_key
echo 'PASS Agent Zero client API key synchronized from the running service'
