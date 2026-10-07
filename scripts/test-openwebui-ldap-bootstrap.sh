#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Fresh-database LDAP bootstrap acceptance for the HADES Open WebUI candidate.
# It uses only pinned local images, synthetic directory accounts, private
# container networking, and disposable bind-mounted WebUI state.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
image=${HADES_OPEN_WEBUI_LDAP_TEST_IMAGE:-hades-open-webui:0.11.4-candidate}
image_id=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null) || {
  echo "FAIL candidate image is not cached: $image" >&2
  exit 2
}
docker image inspect "$HADES_LLDAP_IMAGE" >/dev/null 2>&1 || {
  echo 'FAIL pinned LLDAP image is not cached; refusing an implicit pull' >&2
  exit 2
}

suffix=$$
network="hades-owui-ldap-$suffix"
lldap="hades-owui-ldap-directory-$suffix"
webui="hades-owui-ldap-web-$suffix"
work=$(mktemp -d /tmp/hades-owui-ldap.XXXXXX)
cleanup() {
  docker stop "$webui" "$lldap" >/dev/null 2>&1 || true
  for container in "$webui" "$lldap"; do
    for _ in $(seq 1 50); do
      docker inspect "$container" >/dev/null 2>&1 || break
      sleep 0.1
    done
  done
  docker network rm "$network" >/dev/null 2>&1 || true
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1],ignore_errors=True)' "$work"
}
trap cleanup EXIT INT TERM

mkdir -p "$work/identity" "$work/users" "$work/groups" "$work/data-owner-first" "$work/data-household-first"
printf 'synthetic-jwt-secret-0123456789012345678901234567890123456789\n' > "$work/identity/jwt"
printf 'synthetic-key-seed-012345678901234567890123456789012345678901234567890123456789\n' > "$work/identity/seed"
printf 'synthetic-admin-password\n' > "$work/identity/pass"
cat > "$work/groups/owner.json" <<'EOF'
{"name":"hades-owner"}
EOF
cat > "$work/groups/household.json" <<'EOF'
{"name":"hades-household"}
EOF
cat > "$work/users/owner.json" <<'EOF'
{"id":"synthetic-owner","email":"owner@hades.example.invalid","password":"synthetic-owner-password","displayName":"Synthetic Owner","groups":["hades-owner"]}
EOF
cat > "$work/users/household.json" <<'EOF'
{"id":"synthetic-household","email":"household@hades.example.invalid","password":"synthetic-household-password","displayName":"Synthetic Household","groups":["hades-household"]}
EOF
if [[ "$(id -u)" == 0 ]]; then
  chown -R 1000:1000 "$work/identity" "$work/users" "$work/groups"
fi

docker network create "$network" >/dev/null
docker run --rm -d --name "$lldap" --network "$network" \
  -e UID=1000 -e GID=1000 -e TZ=UTC \
  -e LLDAP_LDAP_BASE_DN=dc=hades,dc=local -e LLDAP_LDAP_USER_DN=admin \
  -e LLDAP_LDAP_USER_EMAIL=admin@hades.example.invalid \
  -e LLDAP_JWT_SECRET_FILE=/run/secrets/jwt -e LLDAP_KEY_SEED_FILE=/run/secrets/seed \
  -e LLDAP_LDAP_USER_PASS_FILE=/run/secrets/pass \
  -v "$work/identity/jwt:/run/secrets/jwt:ro,Z" \
  -v "$work/identity/seed:/run/secrets/seed:ro,Z" \
  -v "$work/identity/pass:/run/secrets/pass:ro,Z" \
  -v "$work/users:/probe/users:ro,Z" -v "$work/groups:/probe/groups:ro,Z" \
  "$HADES_LLDAP_IMAGE" >/dev/null

ready=false
for _ in $(seq 1 90); do
  if docker logs "$lldap" 2>&1 | rg -q 'Starting the LDAP server on port 3890'; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { docker logs --tail 40 "$lldap" >&2; echo 'FAIL LLDAP did not start' >&2; exit 1; }
docker exec -e LLDAP_URL=http://localhost:17170 -e LLDAP_ADMIN_USERNAME=admin \
  -e LLDAP_ADMIN_PASSWORD=synthetic-admin-password -e USER_CONFIGS_DIR=/probe/users \
  -e GROUP_CONFIGS_DIR=/probe/groups -e DO_CLEANUP=false "$lldap" /app/bootstrap.sh >/dev/null

run_order() {
  local order=$1 first=$2 second=$3 first_role=$4 second_role=$5 data_dir="$work/data-$1"
  local port
  docker run --rm -d --name "$webui" --network "$network" -p 127.0.0.1::8080 \
    -e ENABLE_SIGNUP=false -e ENABLE_LOGIN_FORM=true -e ENABLE_LDAP=true \
    -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
    -e LDAP_SERVER_HOST="$lldap" -e LDAP_SERVER_PORT=3890 -e LDAP_USE_TLS=false \
    -e LDAP_APP_DN='uid=admin,ou=people,dc=hades,dc=local' \
    -e LDAP_APP_PASSWORD=synthetic-admin-password \
    -e LDAP_SEARCH_BASE='ou=people,dc=hades,dc=local' \
    -e LDAP_ATTRIBUTE_FOR_USERNAME=uid -e LDAP_ATTRIBUTE_FOR_MAIL=mail \
    -v "$data_dir:/app/backend/data" "$image_id" >/dev/null
  port=$(docker port "$webui" 8080/tcp | sed 's/.*://')
  ready=false
  for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  curl -fsS "http://127.0.0.1:$port/health" >/dev/null || {
    docker logs --tail 40 "$webui" >&2
    echo "FAIL Open WebUI did not become healthy ($order)" >&2
    exit 1
  }
  HADES_TEST_REPO_DIR="$repo_dir" HADES_TEST_SUBJECT_FILE="$work/subjects-$order.json" HADES_TEST_WEBUI_URL="http://127.0.0.1:$port" \
    python3 - "$first" "$second" "$first_role" "$second_role" <<'PY'
import json
import os
from pathlib import Path
import sys
import uuid
import urllib.request
from urllib.error import HTTPError

base = os.environ['HADES_TEST_WEBUI_URL']
first, second, first_role, second_role = sys.argv[1:]
credentials = {
    'synthetic-owner': 'synthetic-owner-password',
    'synthetic-household': 'synthetic-household-password',
}

def login(user):
    req = urllib.request.Request(
        base + '/api/v1/auths/ldap',
        data=json.dumps({'user': user, 'password': credentials[user]}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = json.load(response)
    assert body.get('token'), f'LDAP login returned no token for {user}'
    expected_mail = 'owner@hades.example.invalid' if user == 'synthetic-owner' else 'household@hades.example.invalid'
    assert body.get('email') == expected_mail, f'LDAP email mismatch for {user}'
    return body

def authorized(method, path, token, payload=None, content_type='application/json'):
    data = payload
    if isinstance(payload, dict):
        data = json.dumps(payload).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': content_type, 'Accept': 'application/json'},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, response.read()

one = login(first)
two = login(second)
assert one.get('role') == first_role, (first, one.get('role'), first_role)
assert two.get('role') == second_role, (second, two.get('role'), second_role)
assert one.get('id') and two.get('id') and one['id'] != two['id']
if first == 'synthetic-owner':
    with urllib.request.urlopen(base + '/', timeout=15) as response:
        index = response.read().decode('utf-8', 'replace')
    repo = Path(os.environ['HADES_TEST_REPO_DIR'])
    for asset in ('hades-theme.css', 'hades-theme.js', 'finance-upload.js', 'receipt-upload.js'):
        assert f'/static/{asset}?v=' in index, f'{asset} is not referenced by the served WebUI index'
        with urllib.request.urlopen(base + f'/static/{asset}', timeout=15) as response:
            served = response.read()
        expected = (repo / 'webui' / asset).read_bytes()
        assert served == expected, f'served HADES asset differs from source: {asset}'
    print('PASS served theme and HADES upload assets match the candidate source exactly')
for user, body in ((first, one), (second, two)):
    if body.get('role') != 'pending':
        continue
    req = urllib.request.Request(base + '/api/v1/users/user/info', headers={'Authorization': 'Bearer ' + body['token']})
    try:
        urllib.request.urlopen(req, timeout=15)
    except HTTPError as error:
        assert error.code == 401, (user, error.code)
    else:
        raise AssertionError(f'pending LDAP account can access verified-user route: {user}')
    print(f'PASS pending LDAP account is denied the verified-user API: {user}')
subjects = {
    'synthetic-owner': one['id'] if first == 'synthetic-owner' else two['id'],
    'synthetic-household': one['id'] if first == 'synthetic-household' else two['id'],
}
if first == 'synthetic-owner':
    # The fixture's household LDAP group was verified at directory bootstrap;
    # promote only this account through the supported admin API for the
    # authenticated file-ownership check below.
    household = two
    status, _ = authorized('POST', f"/api/v1/users/{household['id']}/update", one['token'], {'role': 'user'})
    assert status == 200, status
    household = login('synthetic-household')
    assert household.get('role') == 'user', household.get('role')

    boundary = 'hades-test-' + uuid.uuid4().hex
    file_bytes = b'HADES candidate private upload acceptance marker.\n'
    multipart = (
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="file"; filename="synthetic-private.txt"\r\n'
        'Content-Type: text/plain\r\n\r\n'
    ).encode() + file_bytes + f'\r\n--{boundary}--\r\n'.encode()
    status, raw_file = authorized(
        'POST', '/api/v1/files/?process=false', one['token'], multipart,
        f'multipart/form-data; boundary={boundary}',
    )
    uploaded = json.loads(raw_file)
    file_id = uploaded.get('id')
    assert status == 200 and file_id, uploaded
    status, content = authorized('GET', f'/api/v1/files/{file_id}/content', one['token'])
    assert status == 200 and content == file_bytes, (status, content[:100])
    try:
        authorized('GET', f'/api/v1/files/{file_id}/content', household['token'])
    except HTTPError as error:
        assert error.code in (401, 403, 404), error.code
    else:
        raise AssertionError('verified household account retrieved owner-private upload')
    subjects['file_id'] = file_id
    print('PASS authenticated file upload, owner read-back, and household isolation')
with open(os.environ['HADES_TEST_SUBJECT_FILE'], 'w', encoding='utf-8') as stream:
    json.dump(subjects, stream)
print(f"PASS {first} first role={first_role}; {second} second role={second_role}; subjects distinct")
PY

  if [[ "$order" == owner-first ]]; then
    docker restart "$webui" >/dev/null
    # Docker may allocate a different ephemeral host port after restart.
    port=$(docker port "$webui" 8080/tcp | sed 's/.*://')
    ready=false
    for _ in $(seq 1 90); do
      if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then ready=true; break; fi
      sleep 1
    done
    [[ "$ready" == true ]] || { echo 'FAIL Open WebUI did not recover after restart' >&2; exit 1; }
    HADES_TEST_REPO_DIR="$repo_dir" HADES_TEST_SUBJECT_FILE="$work/subjects-owner-first.json" HADES_TEST_WEBUI_URL="http://127.0.0.1:$port" python3 - <<'PY'
import json
import os
import urllib.request
base = os.environ['HADES_TEST_WEBUI_URL']
with open(os.environ['HADES_TEST_SUBJECT_FILE'], encoding='utf-8') as stream: before = json.load(stream)
after = {}
for user, password in [('synthetic-owner', 'synthetic-owner-password'), ('synthetic-household', 'synthetic-household-password')]:
    req = urllib.request.Request(base + '/api/v1/auths/ldap', data=json.dumps({'user': user, 'password': password}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response: current = json.load(response)
    assert current.get('token')
    after[user] = current['id']
assert {key: value for key, value in before.items() if key != 'file_id'} == after, (before, after)
if 'file_id' in before:
    owner_req = urllib.request.Request(base + '/api/v1/auths/ldap', data=json.dumps({'user': 'synthetic-owner', 'password': 'synthetic-owner-password'}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(owner_req, timeout=15) as response: owner = json.load(response)
    content_req = urllib.request.Request(base + f"/api/v1/files/{before['file_id']}/content", headers={'Authorization': 'Bearer ' + owner['token']})
    with urllib.request.urlopen(content_req, timeout=15) as response: content = response.read()
    assert content == b'HADES candidate private upload acceptance marker.\n'
print('PASS owner-first subject separation survives WebUI restart and fresh LDAP login')
if 'file_id' in before: print('PASS owner-private upload persists across WebUI restart')
PY
  fi
  docker stop "$webui" >/dev/null
  for _ in $(seq 1 50); do
    docker inspect "$webui" >/dev/null 2>&1 || break
    sleep 0.1
  done
}

run_order owner-first synthetic-owner synthetic-household admin pending
run_order household-first synthetic-household synthetic-owner admin pending
echo 'PASS disposable Open WebUI 0.11.4 LDAP bootstrap acceptance'
echo 'NOTE first LDAP login becomes admin regardless of LLDAP group; owner-first setup is required'
