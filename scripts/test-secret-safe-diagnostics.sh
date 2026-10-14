#!/usr/bin/env bash
set +x
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
chmod 700 "$work"
sentinel='SYNTHETIC_SECRET_MUST_NOT_APPEAR_IN_DIAGNOSTICS_7f29c1'

# These entrypoints can source protected inputs. Clear inherited bash tracing
# before any input is parsed, even when invoked as `bash -x script`.
for script in install-hades.sh render-deployment-records.sh hades-doctor.sh validate-install.sh upgrade-hades.sh destination-hermes-model-smoke.sh; do
  file="$repo_dir/scripts/$script"
  [[ "$(sed -n '2p' "$file")" == 'set +x' ]] || {
    echo "FAIL $script must disable inherited xtrace immediately after the shebang" >&2
    exit 1
  }
  first_source=$(awk '/^[[:space:]]*(source|\.)[[:space:]]/ { print NR; exit }' "$file")
  [[ -z "$first_source" || "$first_source" -gt 2 ]] || {
    echo "FAIL $script sources files before disabling xtrace" >&2
    exit 1
  }
done
service_exec=$(grep '^ExecStart=' "$repo_dir/deploy/templates/hermes.service.in")
[[ "$service_exec" == *"-c 'set +x; set -a; source "* ]] || {
  echo 'FAIL Hermes service must clear xtrace before sourcing protected environments' >&2
  exit 1
}

cat > "$work/operator.env" <<EOF
SYNTHETIC_SECRET=$sentinel
EOF
chmod 600 "$work/operator.env"
mkdir "$work/out"
chmod 700 "$work/out"

# Exercise a real file-sourcing entrypoint with xtrace deliberately inherited.
# The synthetic secret must not escape through stdout/stderr.
set +e
output=$(bash -x "$repo_dir/scripts/render-deployment-records.sh" "$work/operator.env" "$work/out" 2>&1)
status=$?
set -e
[[ $status -ne 0 ]] || { echo 'FAIL incomplete fixture unexpectedly rendered' >&2; exit 1; }
[[ "$output" != *"$sentinel"* ]] || { echo 'FAIL protected value appeared in traced diagnostics' >&2; exit 1; }

echo 'PASS protected-input entrypoints disable inherited xtrace before sourcing'
