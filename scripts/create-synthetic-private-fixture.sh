#!/usr/bin/env bash
set -Eeuo pipefail

output_dir=${1:-}
if [[ -z "$output_dir" || "$output_dir" != /* ]]; then
  printf 'usage: %s ABSOLUTE_OUTPUT_DIRECTORY\n' "$0" >&2
  exit 2
fi
[[ ! -e "$output_dir" ]] || { printf 'FAIL synthetic fixture output already exists: %s\n' "$output_dir" >&2; exit 1; }
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"

records="$output_dir/records"
identity="$output_dir/identity"
synthetic_image='alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'
mkdir -p "$records" "$identity" "$output_dir/config" "$output_dir/backups" "$output_dir/profile" "$output_dir/state"
chmod 700 "$output_dir" "$identity"

for secret in jwt_secret key_seed admin_password; do
  printf 'synthetic-%s\n' "$secret" > "$identity/$secret"
  chmod 600 "$identity/$secret"
done

for spec in \
  'open-webui.compose.yaml:hades-synthetic-open-webui' \
  'hindsight.compose.yaml:hades-synthetic-hindsight' \
  'searxng.compose.yaml:hades-synthetic-searxng'; do
  record=${spec%%:*}
  project=${spec#*:}
  image="$synthetic_image"
  case "$record" in
    hindsight.compose.yaml) image="$HADES_HINDSIGHT_IMAGE" ;;
    searxng.compose.yaml) image="$HADES_SEARXNG_IMAGE_RECORD" ;;
  esac
  cat > "$records/$record" <<EOF
name: $project
services:
  smoke:
    image: $image
    restart: unless-stopped
    command: ["sleep", "infinity"]
EOF
  chmod 600 "$records/$record"
done

cat > "$records/hermes.service" <<'EOF'
[Unit]
Description=HADES synthetic Hermes runtime

[Service]
Type=simple
ExecStart=/usr/bin/sleep infinity
Restart=always

[Install]
WantedBy=multi-user.target
EOF
chmod 600 "$records/hermes.service"

cat > "$output_dir/operator.env" <<EOF
HADES_INPUTS_VERSION=1
HADES_STATE_ROOT=$output_dir/state
HADES_CONFIG_ROOT=$output_dir/config
HADES_BACKUP_ROOT=$output_dir/backups
HADES_IDENTITY_SECRETS_DIR=$identity
HADES_DEPLOYMENT_DIR=$records
HADES_OPEN_WEBUI_COMPOSE_FILE=$records/open-webui.compose.yaml
HADES_HINDSIGHT_COMPOSE_FILE=$records/hindsight.compose.yaml
HADES_SEARXNG_COMPOSE_FILE=$records/searxng.compose.yaml
HADES_HERMES_SERVICE_FILE=$records/hermes.service
HADES_HERMES_PROFILE=$output_dir/profile
HADES_OWNER_BOOTSTRAP_ID=synthetic-owner
HADES_HERMES_API_KEY=synthetic-key
HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:18080
HADES_HINDSIGHT_DATABASE_SECRET_FILE=$output_dir/hindsight-secret
HADES_GROCY_API_KEY_FILE=$output_dir/grocy-api-key
HADES_AGENT_ZERO_CREDENTIAL_FILE=$output_dir/agent-zero-credential
EOF
chmod 600 "$output_dir/operator.env"
for secret in hindsight-secret grocy-api-key agent-zero-credential; do
  printf 'synthetic-%s\n' "$secret" > "$output_dir/$secret"
  chmod 600 "$output_dir/$secret"
done

printf 'PASS synthetic private fixture created: %s\n' "$output_dir"
