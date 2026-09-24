#!/usr/bin/env bash
set -euo pipefail

# Narrow operational bridge for the staged/future directory-backed deployment.
# It deliberately revokes the application account before the directory entry:
# this closes existing Open WebUI bearer sessions before preventing re-login.
# Tokens and URLs are supplied by the operator and are never written to disk.

usage() {
  echo "usage: $0 USERNAME" >&2
  echo "required env: HADES_LLDAP_URL HADES_OPEN_WEBUI_URL LLDAP_ADMIN_TOKEN OPEN_WEBUI_ADMIN_TOKEN" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
username=$1
[[ "$username" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
  echo "invalid username" >&2
  exit 2
}
: "${HADES_LLDAP_URL:?missing HADES_LLDAP_URL}"
: "${HADES_OPEN_WEBUI_URL:?missing HADES_OPEN_WEBUI_URL}"
: "${LLDAP_ADMIN_TOKEN:?missing LLDAP_ADMIN_TOKEN}"
: "${OPEN_WEBUI_ADMIN_TOKEN:?missing OPEN_WEBUI_ADMIN_TOKEN}"

graphql() {
  curl --fail-with-body --silent --show-error \
    -H "Authorization: Bearer $LLDAP_ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    "$HADES_LLDAP_URL/api/graphql" -d "$1"
}

user_json=$(graphql "{\"query\":\"{ users { id email } }\"}")
email=$(printf '%s' "$user_json" | USERNAME="$username" python -c '
import json, os, sys
x = json.load(sys.stdin)
for user in x.get("data", {}).get("users", []):
    if user.get("id") == os.environ["USERNAME"]:
        print(user.get("email", ""))
        break
') || {
  echo "directory user not found: $username" >&2
  exit 1
}
[[ -n "$email" ]] || { echo "directory user not found: $username" >&2; exit 1; }

webui_users=$(curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $OPEN_WEBUI_ADMIN_TOKEN" \
  "$HADES_OPEN_WEBUI_URL/api/v1/users/")
app_id=$(printf '%s' "$webui_users" | EMAIL="$email" python -c '
import json, os, sys
x = json.load(sys.stdin)
for user in x.get("users", x if isinstance(x, list) else []):
    if user.get("email") == os.environ["EMAIL"]:
        print(user.get("id", ""))
        break
')

if [[ -n "$app_id" ]]; then
  curl --fail-with-body --silent --show-error -X DELETE \
    -H "Authorization: Bearer $OPEN_WEBUI_ADMIN_TOKEN" \
    "$HADES_OPEN_WEBUI_URL/api/v1/users/$app_id" >/dev/null
else
  # A prior run may have removed the application account before an operator
  # lost the response or the directory deletion was attempted. Treat that
  # state as safe to continue; the final email-based verification below still
  # fails closed if an application account is present.
  echo "Open WebUI account already absent; continuing directory revocation" >&2
fi

delete_json=$(graphql "{\"query\":\"mutation { deleteUser(userId: \\\"$username\\\") { ok } }\"}")
[[ "$(printf '%s' "$delete_json" | python -c 'import json,sys; print(json.load(sys.stdin).get("data",{}).get("deleteUser",{}).get("ok"))')" == True ]] || {
  echo "directory deletion was not acknowledged" >&2
  exit 1
}

# Fail closed if either authoritative lookup still exposes the account.
if graphql "{\"query\":\"{ users { id } }\"}" | USERNAME="$username" python -c '
import json, os, sys
x=json.load(sys.stdin)
raise SystemExit(0 if any(u.get("id") == os.environ["USERNAME"] for u in x.get("data",{}).get("users",[])) else 1)
'; then
  echo "directory user still present after revoke" >&2
  exit 1
fi
if curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $OPEN_WEBUI_ADMIN_TOKEN" \
  "$HADES_OPEN_WEBUI_URL/api/v1/users/" | EMAIL="$email" python -c '
import json, os, sys
x=json.load(sys.stdin)
users=x.get("users", x if isinstance(x, list) else [])
raise SystemExit(0 if any(u.get("email") == os.environ["EMAIL"] for u in users) else 1)
'; then
  echo "Open WebUI user still present after revoke: $email" >&2
  exit 1
fi

echo "revoked directory and Open WebUI account: $username"
