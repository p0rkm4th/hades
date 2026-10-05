#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
cleanup() { rm -rf -- "$fixture"; }
trap cleanup EXIT
chmod 0700 "$fixture"
mkdir -p "$fixture/out"
inputs="$fixture/operator.env"
output="$fixture/out/hermes.service"
cat > "$inputs" <<'ENV'
HADES_HERMES_WORKING_DIRECTORY=/opt/hades
HADES_HERMES_EXECUTABLE=/usr/bin/hermes
HADES_HERMES_PROFILE=/etc/hades/hermes
HADES_CONFIG_ROOT=/etc/hades
HADES_DEPLOYMENT_DIR=/etc/hades/private-deployment
HADES_HERMES_RUNTIME_USER=hades-runtime
HADES_HERMES_RUNTIME_GROUP=hades-runtime
HADES_HERMES_API_BIND_HOST=127.0.0.1
HADES_SEARXNG_PORT=8181
ENV
chmod 0600 "$inputs"

bash "$repo_dir/scripts/render-hermes-service.sh" --inputs "$inputs" --output "$output"
test "$(stat -c '%a' "$output")" = 600
grep -Fq 'WorkingDirectory=/opt/hades' "$output"
grep -Fq 'User=hades-runtime' "$output"
grep -Fq 'Group=hades-runtime' "$output"
grep -Fq 'EnvironmentFile=-/etc/hades/hermes/hermes.env' "$output"
grep -Fq 'Environment=HERMES_HOME=/etc/hades/hermes' "$output"
grep -Fq 'Environment=PYTHONPATH=/etc/hades/overlay' "$output"
grep -Fq 'Environment=HADES_HERMES_WORKING_DIRECTORY=/opt/hades' "$output"
grep -Fq 'Environment=SEARXNG_URL=http://127.0.0.1:8181' "$output"
grep -Fq 'EnvironmentFile=-/etc/hades/private-deployment/agent-zero-client-auth.env' "$output"
grep -Fq 'repository_revision=' "$output"
! grep -Fq '@HADES_' "$output"

bash "$repo_dir/scripts/render-hermes-service.sh" --inputs "$inputs" \
  --output "$output" --deployment-dir "$fixture/other-deployment"
grep -Fq "$fixture/other-deployment/agent-zero-client-auth.env" "$output"

unsafe="$fixture/unsafe.env"
cp "$inputs" "$unsafe"
chmod 0644 "$unsafe"
if bash "$repo_dir/scripts/render-hermes-service.sh" --inputs "$unsafe" \
  --output "$fixture/out/unsafe.service" 2>/dev/null; then
  echo 'FAIL Hermes service renderer accepted public-readable inputs' >&2
  exit 1
fi

ln -s "$inputs" "$fixture/input-link.env"
if bash "$repo_dir/scripts/render-hermes-service.sh" --inputs "$fixture/input-link.env" \
  --output "$fixture/out/link.service" 2>/dev/null; then
  echo 'FAIL Hermes service renderer accepted symlinked inputs' >&2
  exit 1
fi

invalid_user="$fixture/invalid-user.env"
sed 's/^HADES_HERMES_RUNTIME_USER=.*/HADES_HERMES_RUNTIME_USER=BadUser/' "$inputs" > "$invalid_user"
chmod 0600 "$invalid_user"
if bash "$repo_dir/scripts/render-hermes-service.sh" --inputs "$invalid_user" \
  --output "$fixture/out/invalid-user.service" 2>/dev/null; then
  echo 'FAIL Hermes service renderer accepted an invalid runtime account name' >&2
  exit 1
fi

echo 'PASS isolated Hermes service unit rendering, mode, and input guards'
