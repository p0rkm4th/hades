#!/usr/bin/env bash
set -Eeuo pipefail

# Disposable populated-database upgrade check. No production data or service is
# mounted; one synthetic 0.11.1 user/chat volume is handed to the candidate.
old_image=${1:?usage: test-open-webui-populated-migration.sh OLD_IMAGE CANDIDATE_IMAGE}
new_image=${2:?usage: test-open-webui-populated-migration.sh OLD_IMAGE CANDIDATE_IMAGE}
bash "$(dirname "$0")/verify-open-web-ui-candidate-artifact.sh" "$new_image"
old_version=$(docker image inspect "$old_image" --format '{{index .Config.Labels "org.opencontainers.image.version"}}')
new_version=$(docker image inspect "$new_image" --format '{{index .Config.Labels "org.opencontainers.image.version"}}')
[[ "$old_version" == 0.11.1 ]] || { echo "FAIL expected old Open WebUI 0.11.1 image, got $old_version" >&2; exit 2; }
[[ "$new_version" == 0.11.4 ]] || { echo "FAIL expected candidate Open WebUI 0.11.4 image, got $new_version" >&2; exit 2; }

suffix=$$
name="hades-open-webui-migration-$suffix"
volume="hades-open-webui-migration-$suffix"
rollback_name="hades-open-webui-rollback-$suffix"
rollback_volume="hades-open-webui-rollback-$suffix"
port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
backend_port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
tmp=$(mktemp -d "${TMPDIR:-/tmp}/hades-open-webui-migration.XXXXXX")
cleanup() {
  docker stop "$name" >/dev/null 2>&1 || true
  docker rm "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  docker stop "$rollback_name" >/dev/null 2>&1 || true
  docker rm "$rollback_name" >/dev/null 2>&1 || true
  docker volume rm "$rollback_volume" >/dev/null 2>&1 || true
  kill "${backend_pid:-}" >/dev/null 2>&1 || true
  find "$tmp" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$tmp" 2>/dev/null || true
}
trap cleanup EXIT

cat > "$tmp/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        body = json.dumps({"data": [{"id": "synthetic-migration-model", "object": "model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps({"id": "synthetic", "object": "chat.completion", "created": 1,
            "model": "synthetic-migration-model", "choices": [{"index": 0,
            "message": {"role": "assistant", "content": "Migration-state-marker-7f2a"},
            "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

ThreadingHTTPServer(("0.0.0.0", int(os.environ["BACKEND_PORT"])), Handler).serve_forever()
PY
BACKEND_PORT="$backend_port" python3 "$tmp/backend.py" >/dev/null 2>&1 &
backend_pid=$!
docker volume create "$volume" >/dev/null

start_image() {
  docker rm "$name" >/dev/null 2>&1 || true
  docker run -d --name "$name" \
    -p "127.0.0.1:${port}:8080" \
    --add-host host.docker.internal:host-gateway \
    -v "$volume:/app/backend/data" \
    -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
    -e WEBUI_SECRET_KEY=synthetic-openwebui-backup-test-key \
    -e ENABLE_CHANNELS=true -e USER_PERMISSIONS_FEATURES_CHANNELS=true \
    "$1" >/dev/null
  for _ in $(seq 1 90); do
    curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -fsS "http://127.0.0.1:${port}/health" >/dev/null
}

start_image "$old_image"
account=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Migration Owner","email":"migration-owner@example.invalid","password":"Synthetic-Only-123!"}')
token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$account")
account_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$account")
beta=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/add" \
  -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  --data '{"name":"Migration Beta","email":"migration-beta@example.invalid","password":"Synthetic-Beta-123!","role":"user"}')
beta_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$beta")
beta_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$beta")
python3 - "$tmp/migration-fixture.docx" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED) as docx:
    docx.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    docx.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    docx.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic migration upload marker 4c91</w:t></w:r></w:p><w:sectPr/></w:body></w:document>')
PY
upload=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/files/?process=false" \
  -H "Authorization: Bearer $token" -F "file=@$tmp/migration-fixture.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document")
file_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$upload")
curl -fsS "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $token" -o "$tmp/upload-before.docx"
cmp "$tmp/migration-fixture.docx" "$tmp/upload-before.docx"
private_file_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $beta_token")
[[ "$private_file_status" == 401 || "$private_file_status" == 403 || "$private_file_status" == 404 ]] || {
  echo "FAIL Beta accessed owner's private uploaded file (HTTP $private_file_status)" >&2
  exit 1
}
curl -fsS -X POST "http://127.0.0.1:${port}/openai/config/update" \
  -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${backend_port}/v1\"],\"OPENAI_API_KEYS\":[\"synthetic\"],\"OPENAI_API_CONFIGS\":{}}" >/dev/null
models=''
for _ in $(seq 1 30); do
  models=$(curl -fsS "http://127.0.0.1:${port}/openai/models" -H "Authorization: Bearer $token")
  rg -q synthetic-migration-model <<<"$models" && break
  sleep 1
done
rg -q synthetic-migration-model <<<"$models"

mid=$(python3 -c 'import uuid; print(uuid.uuid4())')
aid=$(python3 -c 'import uuid; print(uuid.uuid4())')
sid=$(python3 -c 'import uuid; print(uuid.uuid4())')
body=$(python3 -c 'import json,sys; mid,aid,sid=sys.argv[1:]; marker="Migration-state-marker-7f2a"; print(json.dumps({"model":"synthetic-migration-model","messages":[{"id":mid,"role":"user","content":marker}],"stream":False,"parent_id":None,"id":aid,"session_id":sid,"user_message":{"id":mid,"role":"user","content":marker}}))' "$mid" "$aid" "$sid")
status=$(curl -sS -o "$tmp/completion.json" -w '%{http_code}' -X POST \
  "http://127.0.0.1:${port}/api/chat/completions" -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' --data "$body")
[[ "$status" == 200 ]] || { cat "$tmp/completion.json" >&2; exit 1; }
chat_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["chat_id"])' < "$tmp/completion.json")
curl -fsS "http://127.0.0.1:${port}/api/v1/chats/${chat_id}" \
  -H "Authorization: Bearer $token" | rg -q Migration-state-marker-7f2a
channel=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/create" \
  -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"name":"migration-shared","description":"Synthetic migration channel","type":"group","is_private":True,"user_ids":[sys.argv[1]]}))' "$beta_id")")
channel_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$channel")
curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages/post" \
  -H "Authorization: Bearer $beta_token" -H 'Content-Type: application/json' \
  --data '{"content":"Synthetic migration channel marker","data":{},"meta":{}}' >/dev/null
printf 'PASS Open WebUI %s populated fixture accounts, chat, shared channel, and private DOCX upload persisted\n' "$old_version"

# Take a consistent online SQLite backup while the old instance is serving the
# synthetic fixture. This exercises the same database boundary used by recovery.
docker exec "$name" python3 -c 'import sqlite3; src=sqlite3.connect("/app/backend/data/webui.db"); dst=sqlite3.connect("/tmp/hades-openwebui-pre-upgrade.db"); src.backup(dst); dst.close(); src.close()'
docker cp "$name:/tmp/hades-openwebui-pre-upgrade.db" "$tmp/pre-upgrade-webui.db" >/dev/null
docker exec "$name" rm -f /tmp/hades-openwebui-pre-upgrade.db
chmod 600 "$tmp/pre-upgrade-webui.db"
snapshot_integrity=$(python3 -c 'import sqlite3,sys; db=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); print(db.execute("PRAGMA integrity_check").fetchone()[0])' "$tmp/pre-upgrade-webui.db")
[[ "$snapshot_integrity" == ok ]] || { echo "FAIL SQLite snapshot integrity: $snapshot_integrity" >&2; exit 1; }
printf 'PASS SQLite online backup captured synthetic pre-upgrade state; integrity=%s\n' "$snapshot_integrity"

volume_mounts=$(docker inspect "$name" --format '{{json .Mounts}}')
python3 -c 'import json,sys; mounts=json.loads(sys.argv[1]); assert len(mounts)==1 and mounts[0]["Destination"]=="/app/backend/data" and mounts[0]["Name"].startswith("hades-open-webui-migration-"), mounts' "$volume_mounts"
docker stop "$name" >/dev/null
docker rm "$name" >/dev/null
# Capture the complete synthetic application-data volume while the service is
# stopped. This includes SQLite, uploaded file bytes, and any vector state kept
# under /app/backend/data. The signing key remains the explicit synthetic key
# above; production secrets are never read or copied by this harness.
docker run --rm -v "$volume:/data:ro" -v "$tmp:/backup" --entrypoint tar "$old_image" \
  -C /data -czf /backup/pre-upgrade-data.tar.gz .
printf 'PASS full stopped application-data volume snapshot captured (SQLite, uploads, and colocated state)\n'
start_image "$new_image"
login=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"migration-owner@example.invalid","password":"Synthetic-Only-123!"}')
new_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$login")
new_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$login")
[[ "$new_id" == "$account_id" ]] || { echo 'FAIL account identity changed across upgrade' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${port}/api/v1/chats/${chat_id}" \
  -H "Authorization: Bearer $new_token" | rg -q Migration-state-marker-7f2a
curl -fsS "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $new_token" -o "$tmp/upload-after-upgrade.docx"
cmp "$tmp/migration-fixture.docx" "$tmp/upload-after-upgrade.docx"
beta_login=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"migration-beta@example.invalid","password":"Synthetic-Beta-123!"}')
new_beta_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$beta_login")
new_beta_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$beta_login")
[[ "$new_beta_id" == "$beta_id" ]] || { echo 'FAIL Beta identity changed across upgrade' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages" \
  -H "Authorization: Bearer $new_beta_token" | rg -q 'Synthetic migration channel marker'
private_status=$(curl -sS -o "$tmp/private-chat.json" -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/chats/${chat_id}" \
  -H "Authorization: Bearer $new_beta_token")
[[ "$private_status" == 401 || "$private_status" == 403 ]] || {
  echo "FAIL Beta accessed Alpha's private chat after migration (HTTP $private_status)" >&2
  exit 1
}
new_private_file_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $new_beta_token")
[[ "$new_private_file_status" == 401 || "$new_private_file_status" == 403 || "$new_private_file_status" == 404 ]] || {
  echo "FAIL Beta accessed owner's private uploaded file after migration (HTTP $new_private_file_status)" >&2
  exit 1
}
integrity=$(docker exec "$name" python3 -c \
  "import glob,sqlite3; paths=glob.glob('/app/backend/data/*.db'); assert paths; print([(p,sqlite3.connect(p).execute('PRAGMA integrity_check').fetchone()[0]) for p in paths])")
rg -q "'ok'" <<<"$integrity" || { echo "FAIL SQLite integrity check: $integrity" >&2; exit 1; }
logs=$(docker logs "$name" 2>&1)
if rg -qi 'migration failed|alembic upgrade failed|no such column' <<<"$logs"; then
  echo 'FAIL migration error marker found in candidate logs' >&2
  exit 1
fi
printf 'PASS Open WebUI %s migrated populated %s state; both identities, private chat/file isolation, shared membership, uploaded DOCX bytes, and SQLite integrity survived\n' "$new_version" "$old_version"
printf 'PASS SQLite integrity after migration: %s\n' "$integrity"

# Restore the pre-upgrade snapshot into a fresh disposable volume and boot the
# old image with the same synthetic signing key.
docker stop "$name" >/dev/null
docker rm "$name" >/dev/null
docker volume create "$rollback_volume" >/dev/null
docker create --name "$rollback_name" \
  -p "127.0.0.1:${port}:8080" \
  --add-host host.docker.internal:host-gateway \
  -v "$rollback_volume:/app/backend/data" \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e WEBUI_SECRET_KEY=synthetic-openwebui-backup-test-key \
  -e ENABLE_CHANNELS=true -e USER_PERMISSIONS_FEATURES_CHANNELS=true \
  "$old_image" >/dev/null
docker run --rm -v "$rollback_volume:/data" -v "$tmp:/backup:ro" --entrypoint tar "$old_image" \
  -C /data -xzf /backup/pre-upgrade-data.tar.gz
docker start "$rollback_name" >/dev/null
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${port}/health" >/dev/null
rollback_login=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"migration-owner@example.invalid","password":"Synthetic-Only-123!"}')
rollback_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$rollback_login")
rollback_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$rollback_login")
[[ "$rollback_id" == "$account_id" ]] || { echo 'FAIL owner identity changed after snapshot restore' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${port}/api/v1/chats/${chat_id}" \
  -H "Authorization: Bearer $rollback_token" | rg -q Migration-state-marker-7f2a
curl -fsS "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $rollback_token" -o "$tmp/upload-after-rollback.docx"
cmp "$tmp/migration-fixture.docx" "$tmp/upload-after-rollback.docx"
rollback_beta_login=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"migration-beta@example.invalid","password":"Synthetic-Beta-123!"}')
rollback_beta_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$rollback_beta_login")
rollback_beta_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$rollback_beta_login")
[[ "$rollback_beta_id" == "$beta_id" ]] || { echo 'FAIL Beta identity changed after snapshot restore' >&2; exit 1; }
curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages" \
  -H "Authorization: Bearer $rollback_beta_token" | rg -q 'Synthetic migration channel marker'
rollback_private_status=$(curl -sS -o "$tmp/rollback-private-chat.json" -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/chats/${chat_id}" \
  -H "Authorization: Bearer $rollback_beta_token")
[[ "$rollback_private_status" == 401 || "$rollback_private_status" == 403 ]] || {
  echo "FAIL Beta accessed Alpha's private chat after snapshot restore (HTTP $rollback_private_status)" >&2
  exit 1
}
rollback_private_file_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/files/${file_id}/content" \
  -H "Authorization: Bearer $rollback_beta_token")
[[ "$rollback_private_file_status" == 401 || "$rollback_private_file_status" == 403 || "$rollback_private_file_status" == 404 ]] || {
  echo "FAIL Beta accessed owner's private uploaded file after snapshot restore (HTTP $rollback_private_file_status)" >&2
  exit 1
}
rollback_integrity=$(docker exec "$rollback_name" python3 -c \
  'import sqlite3; print(sqlite3.connect("/app/backend/data/webui.db").execute("PRAGMA integrity_check").fetchone()[0])')
[[ "$rollback_integrity" == ok ]] || { echo "FAIL rollback SQLite integrity: $rollback_integrity" >&2; exit 1; }
printf 'PASS rollback restored full synthetic app-data snapshot on Open WebUI %s; owner/Beta identity, chat, channel access, private-chat/file isolation, DOCX bytes, and SQLite integrity survived\n' "$old_version"
