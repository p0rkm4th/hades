#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script=$repo_dir/scripts/destination-hermes-model-smoke.sh
[[ -x "$script" ]] || { echo 'FAIL model smoke script is not executable'; exit 1; }
bash -n "$script"
grep -Fq 'HADES_MODEL_SMOKE_CONFIRM' "$script"
grep -Fq 'API_SERVER_KEY' "$script"
grep -Fq '/v1/models' "$script"
grep -Fq '/v1/chat/completions' "$script"
grep -Fq 'content_length' "$script"
grep -Fq 'umask 077' "$script"
grep -Fq -- '--header "@$headers_file"' "$script"
grep -Fq 'unset API_SERVER_KEY' "$script"
if grep -Fq 'Authorization: Bearer $key"' "$script" || grep -Fq 'echo "$key"' "$script" || grep -Fq 'printf "$key"' "$script"; then
  echo 'FAIL model smoke may expose protected key' >&2
  exit 1
fi
echo 'PASS destination Hermes model smoke is explicit, bounded, and secret-safe'
