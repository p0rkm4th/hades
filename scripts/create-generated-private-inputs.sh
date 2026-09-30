#!/usr/bin/env bash
set -Eeuo pipefail

output=${1:-}
image_ref=${HADES_OPEN_WEBUI_IMAGE:-}
[[ "$output" == /* ]] || { echo 'usage: create-generated-private-inputs.sh ABSOLUTE_OUTPUT [--image-ref IMAGE]' >&2; exit 2; }
shift || true
while (($#)); do
  case "$1" in
    --image-ref) image_ref=${2:?--image-ref needs an immutable image reference}; shift 2 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ ! -e "$output" ]] || { echo "FAIL output already exists: $output" >&2; exit 1; }
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z "$image_ref" ]]; then
  image_ref=$(bash "$repo_dir/scripts/build-open-webui-artifact.sh" | awk -F= '$1 == "HADES_OPEN_WEBUI_IMAGE" {print substr($0,index($0,"=")+1)}')
fi
[[ "$image_ref" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL Open WebUI artifact reference is not immutable' >&2; exit 1; }
mkdir -p "$output/identity" "$output/secrets" "$output/state" "$output/config" "$output/backups" "$output/profile/profiles/hades"
chmod 0711 "$output"
chmod 0700 "$output/identity" "$output/secrets" "$output/state" "$output/config" "$output/backups" "$output/profile"
chmod 0700 "$output/profile/profiles" "$output/profile/profiles/hades"
model_endpoint=http://127.0.0.1:18080/v1
hermes_api_key=synthetic-hermes-key
hermes_bind_host=172.17.0.1
sed -e "s#http://ollama-host:11434/v1#$model_endpoint#" \
  -e 's/^  default: .*/  default: synthetic-reconstruction-model/' \
  "$repo_dir/hermes/config.yaml.example" > "$output/profile/config.yaml"
cp "$output/profile/config.yaml" "$output/profile/profiles/hades/config.yaml"
chmod 600 "$output/profile/config.yaml" "$output/profile/profiles/hades/config.yaml"
cat > "$output/profile/hermes.env" <<EOF
API_SERVER_ENABLED=true
API_SERVER_HOST=$hermes_bind_host
API_SERVER_PORT=8642
API_SERVER_KEY=$hermes_api_key
API_SERVER_MODEL_NAME=hermes-agent
HERMES_MAX_ITERATIONS=12
HADES_GROCY_URL=http://127.0.0.1:7003
HADES_GROCY_API_KEY_FILE=$output/config/secrets/grocy-api-key
HADES_HERMES_WORKING_DIRECTORY=$repo_dir
EOF
chmod 600 "$output/profile/hermes.env"
for secret in jwt_secret key_seed admin_password; do
  printf 'synthetic-%s\n' "$secret" > "$output/identity/$secret"
  chmod 600 "$output/identity/$secret"
done
ldap_app_password=$(<"$output/identity/admin_password")
printf 'REQUIRED_GROCY_UI_API_KEY\n' > "$output/secrets/grocy-api-key"
chmod 600 "$output/secrets/grocy-api-key"
printf 'synthetic-searxng-secret\n' > "$output/secrets/searxng-secret"
chmod 600 "$output/secrets/searxng-secret"
openssl rand -hex 32 > "$output/secrets/open-webui-secret"
chmod 600 "$output/secrets/open-webui-secret"
cat > "$output/operator.env" <<EOF
HADES_INPUTS_VERSION=2
HADES_SYNTHETIC_FIXTURE=true
HADES_STATE_ROOT=$output/state
HADES_CONFIG_ROOT=$output/config
HADES_BACKUP_ROOT=$output/backups
HADES_IDENTITY_SECRETS_DIR=$output/identity
HADES_DEPLOYMENT_DIR=$output/config/private-deployment
HADES_HERMES_PROFILE=$output/profile
HADES_HERMES_API_KEY=$hermes_api_key
HADES_HERMES_API_BIND_HOST=$hermes_bind_host
HADES_GROCY_URL=http://127.0.0.1:7003
HADES_GROCY_API_KEY_FILE=$output/secrets/grocy-api-key
HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:18080
HADES_HERMES_API_BASE_URL=http://127.0.0.1:8642/v1
HADES_OPEN_WEBUI_BIND=127.0.0.1:3000
HADES_OPEN_WEBUI_LDAP_APP_PASSWORD=$ldap_app_password
# Host URLs above are used by installer preflight. These container URLs use
# the Docker host gateway during a full-stack reconstruction.
HADES_HERMES_CONTAINER_MODEL_ENDPOINT=http://host.docker.internal:18080
HADES_HERMES_CONTAINER_API_BASE_URL=http://host.docker.internal:8642/v1
HADES_OPEN_WEBUI_IMAGE=$image_ref
HADES_OPEN_WEBUI_DATA=$output/state/open-webui
HADES_OPEN_WEBUI_SECRET_SOURCE=$output/secrets/open-webui-secret
HADES_HINDSIGHT_DATA=$output/state/hindsight
HADES_SEARXNG_DATA=$output/state/searxng
HADES_HINDSIGHT_LLM_API_KEY=synthetic-hindsight-key
HADES_SEARXNG_SECRET_FILE=$output/secrets/searxng-secret
HADES_HERMES_WORKING_DIRECTORY=$repo_dir
HADES_HERMES_EXECUTABLE=/opt/hades-hermes/bin/hermes
HADES_HERMES_RUNTIME_USER=hades-runtime
HADES_HERMES_RUNTIME_GROUP=hades-runtime
HADES_OWNER_SUBJECT_IDS=
HADES_AGENT_ZERO_CREDENTIAL_FILE=
HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=
EOF
chmod 600 "$output/operator.env"
printf 'PASS generated v2 private inputs: %s\n' "$output"
printf 'SYNTHETIC TEST DATA ONLY: this bundle is rejected by production install, doctor, and validation.\n' >&2
printf 'Grocy bootstrap required: replace the explicit key placeholder with a key issued by this test Grocy instance before full install.\n' >&2
