#!/usr/bin/env bash
set -Eeuo pipefail
doc=docs/private-input-contract.md
[[ -f "$doc" ]] || { echo 'FAIL private input contract missing'; exit 1; }
grep -q '^HADES_INPUTS_VERSION=1$' config/operator-inputs.env.example || { echo 'FAIL operator input template version is missing'; exit 1; }
grep -q '^HADES_INPUTS_VERSION=2$' config/operator-inputs-v2.env.example || { echo 'FAIL production v2 operator input template is missing'; exit 1; }
if grep -q '^HADES_SYNTHETIC_FIXTURE=true$' config/operator-inputs-v2.env.example; then echo 'FAIL production v2 operator template is marked synthetic'; exit 1; fi
for field in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE HADES_HERMES_WORKING_DIRECTORY HADES_HERMES_EXECUTABLE HADES_HERMES_API_BIND_HOST HADES_HERMES_API_BASE_URL HADES_HERMES_CONTAINER_API_BASE_URL HADES_HERMES_API_KEY HADES_HERMES_MODEL_ENDPOINT HADES_HERMES_CONTAINER_MODEL_ENDPOINT HADES_OLLAMA_BASE_URLS HADES_FAST_OLLAMA_API_BASE_URL HADES_OPEN_WEBUI_BIND HADES_OPEN_WEBUI_LDAP_APP_PASSWORD HADES_OPEN_WEBUI_IMAGE HADES_OPEN_WEBUI_DATA HADES_OPEN_WEBUI_SECRET_SOURCE HADES_HINDSIGHT_DATA HADES_SEARXNG_DATA HADES_HINDSIGHT_LLM_API_KEY HADES_SEARXNG_SECRET_FILE HADES_GROCY_API_KEY_FILE HADES_GROCY_URL HADES_OWNER_SUBJECT_IDS; do
  grep -q "^$field=" config/operator-inputs-v2.env.example || { echo "FAIL v2 operator input template omits $field"; exit 1; }
done
placeholder_log=$(mktemp)
trap 'rm -f "$placeholder_log"' EXIT
if bash scripts/install-hades.sh --inputs config/operator-inputs-v2.env.example --preflight >"$placeholder_log" 2>&1; then
  echo 'FAIL production preflight accepted the unfilled v2 template' >&2
  exit 1
fi
grep -q '^FAIL operator input still contains a REQUIRED_ placeholder$' "$placeholder_log" || {
  echo 'FAIL production preflight did not identify template placeholders' >&2
  exit 1
}
grep -q 'unsupported operator input contract version' scripts/install-hades.sh || { echo 'FAIL installer does not reject unsupported input versions'; exit 1; }
grep -q 'operator input path must be absolute' scripts/install-hades.sh || { echo 'FAIL installer does not reject relative input paths'; exit 1; }
grep -q 'must not be a symlink' scripts/install-hades.sh || { echo 'FAIL installer does not reject symlinked private inputs'; exit 1; }
grep -q 'validate_secret_file' scripts/install-hades.sh || { echo 'FAIL installer does not validate referenced secret files'; exit 1; }
grep -q 'secret-file input must be mode 0600 or 0640' scripts/install-hades.sh || { echo 'FAIL installer does not enforce referenced secret permissions'; exit 1; }
grep -q 'private deployment records must be mode 0600 or 0640' scripts/install-hades.sh || { echo 'FAIL installer does not restrict private record permissions'; exit 1; }
grep -q 'Hindsight private record does not use config/versions.env:HADES_HINDSIGHT_IMAGE' scripts/install-hades.sh || { echo 'FAIL installer does not enforce Hindsight manifest image'; exit 1; }
grep -q 'SearXNG private record does not use config/versions.env:HADES_SEARXNG_IMAGE_RECORD' scripts/install-hades.sh || { echo 'FAIL installer does not enforce SearXNG manifest image'; exit 1; }
grep -q 'private deployment record contains a mutable image reference' scripts/install-hades.sh || { echo 'FAIL installer does not reject mutable private image references'; exit 1; }
grep -q 'export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD' scripts/install-hades.sh || { echo 'FAIL installer does not export all manifest image pins'; exit 1; }
for field in HADES_HERMES_API_KEY HADES_HERMES_MODEL_ENDPOINT HADES_IDENTITY_SECRETS_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE HADES_HERMES_EXECUTABLE HADES_OPEN_WEBUI_IMAGE HADES_OPEN_WEBUI_DATA HADES_HINDSIGHT_DATA HADES_SEARXNG_DATA HADES_HINDSIGHT_LLM_API_KEY HADES_SEARXNG_SECRET_FILE HADES_INPUTS_VERSION HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE HADES_HINDSIGHT_DATABASE_SECRET_FILE HADES_GROCY_API_KEY_FILE HADES_AGENT_ZERO_CREDENTIAL_FILE HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE HADES_SEARXNG_PRIVATE_SETTINGS_FILE HADES_ACTUAL_ENDPOINT HADES_HOMELAB_ENDPOINT HADES_HOME_ASSISTANT_ENDPOINT; do
  grep -Fq "$field" "$doc" || { echo "FAIL private input contract omits $field"; exit 1; }
done
for phrase in 'Required' 'Read permission' 'Regenerate / rotation' 'Backup'; do
  grep -Fq "$phrase" "$doc" || { echo "FAIL private input contract omits $phrase"; exit 1; }
done
if grep -Eq 'sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH|PRIVATE)' "$doc"; then echo 'FAIL private secret in public contract'; exit 1; fi
echo 'PASS private input and secret lifecycle contract'
