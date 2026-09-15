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
mkdir -p "$output/identity" "$output/secrets" "$output/state" "$output/config" "$output/backups" "$output/profile"
chmod 700 "$output" "$output/identity" "$output/secrets"
for secret in jwt_secret key_seed admin_password; do
  printf 'synthetic-%s\n' "$secret" > "$output/identity/$secret"
  chmod 600 "$output/identity/$secret"
done
for secret in hindsight-database grocy-api-key agent-zero-credential searxng-secret; do
  printf 'synthetic-%s\n' "$secret" > "$output/secrets/$secret"
  chmod 600 "$output/secrets/$secret"
done
cat > "$output/operator.env" <<EOF
HADES_INPUTS_VERSION=2
HADES_STATE_ROOT=$output/state
HADES_CONFIG_ROOT=$output/config
HADES_BACKUP_ROOT=$output/backups
HADES_IDENTITY_SECRETS_DIR=$output/identity
HADES_DEPLOYMENT_DIR=$output/config/private-deployment
HADES_HERMES_PROFILE=$output/profile
HADES_OWNER_BOOTSTRAP_ID=synthetic-owner
HADES_HERMES_API_KEY=synthetic-hermes-key
HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:18080
HADES_HERMES_API_BASE_URL=http://127.0.0.1:8642/v1
HADES_OPEN_WEBUI_IMAGE=$image_ref
HADES_OPEN_WEBUI_DATA=$output/state/open-webui
HADES_HINDSIGHT_DATA=$output/state/hindsight
HADES_SEARXNG_DATA=$output/state/searxng
HADES_HINDSIGHT_LLM_API_KEY=synthetic-hindsight-key
HADES_SEARXNG_SECRET_FILE=$output/secrets/searxng-secret
HADES_HERMES_WORKING_DIRECTORY=$repo_dir
HADES_HERMES_EXECUTABLE=/opt/hades-hermes/bin/hermes
HADES_HINDSIGHT_DATABASE_SECRET_FILE=$output/secrets/hindsight-database
HADES_GROCY_API_KEY_FILE=$output/secrets/grocy-api-key
HADES_AGENT_ZERO_CREDENTIAL_FILE=$output/secrets/agent-zero-credential
EOF
chmod 600 "$output/operator.env"
printf 'PASS generated v2 private inputs: %s\n' "$output"
