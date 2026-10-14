#!/usr/bin/env bash
set +x
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
chmod 700 "$work"
sentinel='SYNTHETIC_SECRET_MUST_NOT_APPEAR_IN_DIAGNOSTICS_7f29c1'

# These entrypoints can source protected inputs. Clear inherited shell tracing
# before any input is parsed, even when invoked as `bash -x script`.
for script in install-hades.sh render-deployment-records.sh hades-doctor.sh validate-install.sh upgrade-hades.sh destination-hermes-model-smoke.sh backup-sqlite-state.sh sync-agent-zero-client-auth.sh proxmox-bootstrap.sh check-home-assistant-readonly-config.sh check-homelab-readonly-config.sh revoke-directory-user.sh create-generated-private-inputs.sh; do
  file="$repo_dir/scripts/$script"
  [[ "$(sed -n '2p' "$file")" == 'set +x +v' ]] || {
    echo "FAIL $script must disable inherited shell tracing immediately after the shebang" >&2
    exit 1
  }
  first_source=$(awk '/^[[:space:]]*(source|\.)[[:space:]]/ { print NR; exit }' "$file")
  [[ -z "$first_source" || "$first_source" -gt 2 ]] || {
    echo "FAIL $script sources files before disabling xtrace" >&2
    exit 1
  }
done
service_exec=$(grep '^ExecStart=' "$repo_dir/deploy/templates/hermes.service.in")
[[ "$service_exec" == *"-c 'set +x +v; set -a; source "* ]] || {
  echo 'FAIL Hermes service must clear inherited shell tracing before sourcing protected environments' >&2
  exit 1
}

cat > "$work/operator.env" <<EOF
SYNTHETIC_SECRET=$sentinel
EOF
chmod 600 "$work/operator.env"
mkdir "$work/out"
chmod 700 "$work/out"

for mode in -x -v; do
  # Exercise a real file-sourcing entrypoint with inherited tracing. The
  # synthetic value must not escape through stdout/stderr.
  set +e
  output=$(bash "$mode" "$repo_dir/scripts/render-deployment-records.sh" "$work/operator.env" "$work/out" 2>&1)
  status=$?
  set -e
  [[ $status -ne 0 ]] || { echo "FAIL incomplete fixture unexpectedly rendered under $mode" >&2; exit 1; }
  [[ "$output" != *"$sentinel"* ]] || { echo "FAIL protected value appeared in $mode diagnostics" >&2; exit 1; }
done

# Exercise the token-sync helper against a fake container. A synthetic token
# must be written only to the protected fixture and never appear in diagnostics,
# even if xtrace or verbose mode is inherited by the helper.
mkdir -m 700 "$work/bin" "$work/agent-zero"
cat > "$work/bin/docker" <<'DOCKER'
#!/usr/bin/env sh
printf '%s\n' "$SYNTHETIC_AGENT_ZERO_TOKEN"
DOCKER
chmod 700 "$work/bin/docker"
synthetic_token='SYNTHKEY_1234567'
for mode in -x -v; do
  set +e
  output=$(SYNTHETIC_AGENT_ZERO_TOKEN="$synthetic_token" PATH="$work/bin:$PATH" \
    bash "$mode" "$repo_dir/scripts/sync-agent-zero-client-auth.sh" \
      "$work/agent-zero/agent-zero-client-auth.env" synthetic-container 2>&1)
  status=$?
  set -e
  [[ $status -eq 0 ]] || { echo "FAIL Agent Zero token sync failed under $mode" >&2; exit 1; }
  [[ "$output" != *"$synthetic_token"* ]] || { echo "FAIL synthetic token appeared in $mode diagnostics" >&2; exit 1; }
done
grep -Fqx "AGENT_ZERO_API_KEY=$synthetic_token" "$work/agent-zero/agent-zero-client-auth.env" || {
  echo 'FAIL Agent Zero token sync did not write its protected synthetic result' >&2
  exit 1
}

echo 'PASS Agent Zero token sync keeps synthetic token out of diagnostics'

# The SQLite backup only needs to detect whether Redis backs Open WebUI auth
# state. It must not retain the container's complete environment in a traced
# shell variable, which could expose API credentials.
backup="$repo_dir/scripts/backup-sqlite-state.sh"
if grep -Fq 'webui_env=$(docker inspect' "$backup"; then
  echo 'FAIL backup helper captures the complete Open WebUI environment' >&2
  exit 1
fi
grep -Fq "if docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' hades-open-webui 2>/dev/null | grep -q '^REDIS_URL='; then" "$backup" || {
  echo 'FAIL backup helper no longer checks Redis configuration without retaining the environment' >&2
  exit 1
}

echo 'PASS backup helper checks auth-state configuration without capturing container secrets'
echo 'PASS protected-input entrypoints disable inherited xtrace and verbose mode before sourcing'
