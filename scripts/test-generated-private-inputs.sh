#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
image='alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'
bash "$repo_dir/scripts/create-generated-private-inputs.sh" "$fixture/private" --image-ref "$image" >/dev/null
printf 'synthetic-agent-zero-operator-password-123456\n' > "$fixture/private/secrets/agent-zero-operator-password"
chmod 600 "$fixture/private/secrets/agent-zero-operator-password"
sed "s#^HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=.*#HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=$fixture/private/secrets/agent-zero-operator-password#" \
  "$fixture/private/operator.env" > "$fixture/private/operator.env.next"
mv "$fixture/private/operator.env.next" "$fixture/private/operator.env"
chmod 600 "$fixture/private/operator.env"
grep -q '^HADES_INPUTS_VERSION=2$' "$fixture/private/operator.env"
grep -q '^HADES_SYNTHETIC_FIXTURE=true$' "$fixture/private/operator.env"
grep -q '^HADES_OPEN_WEBUI_IMAGE='"$image"'$' "$fixture/private/operator.env"
grep -Fqx 'REQUIRED_GROCY_UI_API_KEY' "$fixture/private/secrets/grocy-api-key"
[[ "$(stat -c '%a' "$fixture/private/secrets/grocy-api-key")" == 600 ]]
if bash "$repo_dir/scripts/install-hades.sh" --inputs "$fixture/private/operator.env" --preflight >"$fixture/production-install.out" 2>&1; then
  echo 'FAIL synthetic v2 inputs were accepted by production install' >&2
  exit 1
fi
grep -q '^FAIL synthetic fixture inputs are test-only' "$fixture/production-install.out"
if bash "$repo_dir/scripts/hades-doctor.sh" --inputs "$fixture/private/operator.env" >"$fixture/production-doctor.out" 2>&1; then
  echo 'FAIL synthetic v2 inputs were accepted by production doctor' >&2
  exit 1
fi
grep -q '^FAIL synthetic fixture inputs are test-only' "$fixture/production-doctor.out"
if bash "$repo_dir/scripts/validate-install.sh" --inputs "$fixture/private/operator.env" >"$fixture/production-validator.out" 2>&1; then
  echo 'FAIL synthetic v2 inputs were accepted by production validation' >&2
  exit 1
fi
grep -q '^FAIL synthetic fixture inputs are test-only' "$fixture/production-validator.out"
if bash "$repo_dir/scripts/install-hades.sh" --synthetic-deployment-test --inputs "$fixture/private/operator.env" >"$fixture/unauthorized-synthetic.out" 2>&1; then
  echo 'FAIL full synthetic install accepted without machine-bound target authorization' >&2; exit 1
fi
grep -q '^FAIL synthetic deployment target:' "$fixture/unauthorized-synthetic.out"
if bash "$repo_dir/scripts/hades-doctor.sh" --synthetic-deployment-test --inputs "$fixture/private/operator.env" >"$fixture/unauthorized-synthetic.out" 2>&1; then
  echo 'FAIL full synthetic doctor accepted without machine-bound target authorization' >&2; exit 1
fi
grep -q '^FAIL synthetic deployment target:' "$fixture/unauthorized-synthetic.out"
if bash "$repo_dir/scripts/validate-install.sh" --synthetic-deployment-test --inputs "$fixture/private/operator.env" >"$fixture/unauthorized-synthetic.out" 2>&1; then
  echo 'FAIL full synthetic validation accepted without machine-bound target authorization' >&2; exit 1
fi
grep -q '^FAIL synthetic deployment target:' "$fixture/unauthorized-synthetic.out"
test "$(stat -c '%a' "$fixture/private")" = 711
for dir in identity secrets state config backups profile; do test "$(stat -c '%a' "$fixture/private/$dir")" = 700; done
grep -Fqx "HADES_OPEN_WEBUI_SECRET_SOURCE=$fixture/private/secrets/open-webui-secret" "$fixture/private/operator.env"
test -f "$fixture/private/secrets/open-webui-secret" && test "$(stat -c '%a' "$fixture/private/secrets/open-webui-secret")" = 600
ldap_app_password=$(<"$fixture/private/identity/admin_password")
grep -Fqx "HADES_OPEN_WEBUI_LDAP_APP_PASSWORD=$ldap_app_password" "$fixture/private/operator.env"
grep -Fqx 'HADES_OWNER_SUBJECT_IDS=' "$fixture/private/operator.env"
grep -Fq 'LDAP_USE_TLS: "${HADES_OPEN_WEBUI_LDAP_USE_TLS:-false}"' "$repo_dir/deploy/templates/open-webui.compose.yaml"
unset ldap_app_password
test -f "$fixture/private/profile/config.yaml" && test "$(stat -c '%a' "$fixture/private/profile/config.yaml")" = 600
test -f "$fixture/private/profile/profiles/hades/config.yaml" && test "$(stat -c '%a' "$fixture/private/profile/profiles/hades/config.yaml")" = 600
grep -q '^  default: synthetic-reconstruction-model$' "$fixture/private/profile/profiles/hades/config.yaml"
test -f "$fixture/private/profile/hermes.env" && test "$(stat -c '%a' "$fixture/private/profile/hermes.env")" = 600
grep -Fqx "HADES_HERMES_WORKING_DIRECTORY=$repo_dir" "$fixture/private/profile/hermes.env"
for name in jwt_secret key_seed admin_password; do
  test "$(stat -c '%a' "$fixture/private/identity/$name")" = 600
done
for name in grocy-api-key searxng-secret; do
  test "$(stat -c '%a' "$fixture/private/secrets/$name")" = 600
done
test ! -e "$fixture/private/secrets/hindsight-database"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/private/operator.env" "$fixture/private/config/private-deployment" >/dev/null
test ! -e "$fixture/private/config/private-deployment/hades-owner-policy.env"
mkdir -p "$fixture/test-install-root"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$fixture/test-install-root" --inputs "$fixture/private/operator.env" >/dev/null
sed 's/^HADES_OPEN_WEBUI_LDAP_APP_PASSWORD=.*/HADES_OPEN_WEBUI_LDAP_APP_PASSWORD=incorrect-synthetic-password/' \
  "$fixture/private/operator.env" > "$fixture/private/operator-mismatch.env"
chmod 600 "$fixture/private/operator-mismatch.env"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$fixture/mismatch-root" --inputs "$fixture/private/operator-mismatch.env" >"$fixture/ldap-mismatch.log" 2>&1; then
  echo 'FAIL installer accepted an LDAP bind password that differs from LLDAP' >&2
  exit 1
fi
grep -q '^FAIL v2 Open WebUI LDAP bind password does not match' "$fixture/ldap-mismatch.log"
test -f "$fixture/private/config/searxng/settings.yml"
test "$(stat -c '%a' "$fixture/private/config/private-deployment/agent-zero-operator-auth.env")" = 600
grep -qx 'AUTH_LOGIN=hades-operator' "$fixture/private/config/private-deployment/agent-zero-operator-auth.env"
grep -qx 'AUTH_PASSWORD=synthetic-agent-zero-operator-password-123456' "$fixture/private/config/private-deployment/agent-zero-operator-auth.env"
! grep -R 'synthetic-searxng-secret' "$fixture/private/config/private-deployment" >/dev/null
grep -q '^HADES_HERMES_CONTAINER_API_BASE_URL=http://host.docker.internal:8642/v1$' "$fixture/private/operator.env"
grep -q '^HADES_HERMES_CONTAINER_MODEL_ENDPOINT=http://host.docker.internal:18080$' "$fixture/private/operator.env"
grep -q '^HADES_OPEN_WEBUI_BIND=127.0.0.1:3000$' "$fixture/private/operator.env"
grep -Fqx "HADES_GROCY_API_KEY_FILE=$fixture/private/secrets/grocy-api-key" "$fixture/private/operator.env"
grep -Fqx "HADES_GROCY_API_KEY_FILE=$fixture/private/config/secrets/grocy-api-key" "$fixture/private/profile/hermes.env"
grep -q '^  grocy:$' "$fixture/private/profile/config.yaml"
grep -q 'integrations/grocy-mcp/launch.py' "$fixture/private/profile/config.yaml"
grep -q 'GROCY_API_KEY_FILE: "${HADES_GROCY_API_KEY_FILE}"' "$fixture/private/profile/config.yaml"
! grep -q 'GROCY_API_KEY:' "$fixture/private/profile/config.yaml"
! grep -q '^GROCY_API_KEY=' "$fixture/private/profile/hermes.env"
! grep -R -E '/home/[[:alnum:]_.-]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+(:[0-9]+)?|192\.168\.[0-9]+\.[0-9]+|https?://[^/[:space:]]+:11434' "$fixture/private/profile" >/dev/null
api_key=$(sed -n 's/^HADES_HERMES_API_KEY=//p' "$fixture/private/operator.env")
test -n "$api_key"
grep -qx "API_SERVER_KEY=$api_key" "$fixture/private/profile/hermes.env"
grep -qx 'API_SERVER_HOST=172.17.0.1' "$fixture/private/profile/hermes.env"
grep -qx 'HADES_HERMES_API_BIND_HOST=172.17.0.1' "$fixture/private/operator.env"
grep -q 'Environment=API_SERVER_HOST=172.17.0.1' "$fixture/private/config/private-deployment/hermes.service"
bash "$repo_dir/scripts/hades-doctor.sh" --inputs "$fixture/private/operator.env" --test-mode > "$fixture/doctor.out"
grep -q '^PASS Agent Zero native auth configuration$' "$fixture/doctor.out"
printf 'different-synthetic-agent-zero-password-123456\n' > "$fixture/private/secrets/agent-zero-operator-password"
chmod 600 "$fixture/private/secrets/agent-zero-operator-password"
if bash "$repo_dir/scripts/hades-doctor.sh" --inputs "$fixture/private/operator.env" --test-mode > "$fixture/doctor-stale.out"; then
  echo 'FAIL doctor accepted stale rendered Agent Zero auth' >&2
  exit 1
fi
grep -q '^FAIL Agent Zero native auth configuration is malformed or stale$' "$fixture/doctor-stale.out"
echo 'PASS generated v2 private-input bundle'
