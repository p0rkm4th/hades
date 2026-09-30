#!/usr/bin/env bash
set -Eeuo pipefail

# Bounded private destination smoke check. It validates model execution only;
# it is not owner authentication or normal-endpoint acceptance.

destination_ssh=${1:?usage: destination-hermes-model-smoke.sh SSH_TARGET PROFILE_ENV [API_HOST] [API_PORT]}
profile_env=${2:?usage: destination-hermes-model-smoke.sh SSH_TARGET PROFILE_ENV [API_HOST] [API_PORT]}
api_host=${3:-172.17.0.1}
api_port=${4:-8642}

[[ "${HADES_MODEL_SMOKE_CONFIRM:-}" == 1 ]] || {
  echo 'FAIL set HADES_MODEL_SMOKE_CONFIRM=1 to authorize a bounded model smoke request' >&2
  exit 2
}
[[ "$profile_env" == /* && "$api_host" != *[[:space:]]* && "$api_port" =~ ^[0-9]+$ ]] || {
  echo 'FAIL invalid private model smoke input' >&2
  exit 2
}

ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
  bash -s -- "$profile_env" "$api_host" "$api_port" <<'REMOTE_MODEL_SMOKE'
set -Eeuo pipefail
umask 077
profile_env=$1
api_host=$2
api_port=$3
source "$profile_env"
key=${API_SERVER_KEY:?API_SERVER_KEY missing from protected profile}
unset API_SERVER_KEY
models_file=$(mktemp)
response_file=$(mktemp)
request_file=$(mktemp)
headers_file=$(mktemp)
printf 'Authorization: Bearer %s\n' "$key" > "$headers_file"
trap 'rm -f "$models_file" "$response_file" "$request_file" "$headers_file"' EXIT
base="http://${api_host}:${api_port}"
curl -fsS --connect-timeout 3 --max-time 15 \
  --header "@$headers_file" "$base/v1/models" > "$models_file"
model=$(python3 - "$models_file" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
models = data.get("data") or []
if not models or not models[0].get("id"):
    raise SystemExit("no model advertised")
print(models[0]["id"])
PY
)
python3 - "$model" > "$request_file" <<'PY'
import json, sys
print(json.dumps({
    "model": sys.argv[1],
    "messages": [{"role": "user", "content": "Reply with the single word READY."}],
    "stream": False,
}))
PY
curl -fsS --connect-timeout 3 --max-time 30 \
  --header "@$headers_file" \
  -H 'Content-Type: application/json' \
  --data-binary "@$request_file" "$base/v1/chat/completions" > "$response_file"
python3 - "$response_file" "$model" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
choices = data.get("choices") or []
content = ""
if choices:
    content = ((choices[0].get("message") or {}).get("content") or "")
if not isinstance(content, str) or not content.strip():
    raise SystemExit("model response was empty")
print(f"PASS Hermes model smoke model={sys.argv[2]} content_length={len(content)}")
PY
REMOTE_MODEL_SMOKE
