#!/usr/bin/env bash
set -Eeuo pipefail
doc=docs/private-input-contract.md
[[ -f "$doc" ]] || { echo 'FAIL private input contract missing'; exit 1; }
grep -q '^HADES_INPUTS_VERSION=1$' config/operator-inputs.env.example || { echo 'FAIL operator input template version is missing'; exit 1; }
grep -q 'unsupported operator input contract version' scripts/install-hades.sh || { echo 'FAIL installer does not reject unsupported input versions'; exit 1; }
for field in HADES_OWNER_BOOTSTRAP_ID HADES_HERMES_API_KEY HADES_HERMES_MODEL_ENDPOINT HADES_IDENTITY_SECRETS_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE HADES_INPUTS_VERSION HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE HADES_HINDSIGHT_DATABASE_SECRET_FILE HADES_GROCY_API_KEY_FILE HADES_AGENT_ZERO_CREDENTIAL_FILE HADES_SEARXNG_PRIVATE_SETTINGS_FILE HADES_ACTUAL_ENDPOINT HADES_HOMELAB_ENDPOINT HADES_HOME_ASSISTANT_ENDPOINT; do
  grep -Fq "$field" "$doc" || { echo "FAIL private input contract omits $field"; exit 1; }
done
for phrase in 'Required' 'Read permission' 'Regenerate / rotation' 'Backup'; do
  grep -Fq "$phrase" "$doc" || { echo "FAIL private input contract omits $phrase"; exit 1; }
done
if grep -Eq 'sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH|PRIVATE)' "$doc"; then echo 'FAIL private secret in public contract'; exit 1; fi
echo 'PASS private input and secret lifecycle contract'
