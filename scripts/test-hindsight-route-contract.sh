#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

template="$repo_dir/deploy/templates/hindsight.compose.yaml"
grep -q 'HADES_HINDSIGHT_LLM_BASE_URL' "$template" || {
  echo 'FAIL Hindsight compose has no dedicated model endpoint override'
  exit 1
}
grep -q 'HADES_HINDSIGHT_LLM_MODEL' "$template" || {
  echo 'FAIL Hindsight compose has no dedicated model selection override'
  exit 1
}
[[ "$(grep -c '^[[:space:]]*HINDSIGHT_API_LLM_MODEL:' "$template")" == 1 ]] || {
  echo 'FAIL Hindsight compose must declare one extraction model value'
  exit 1
}
grep -q 'HADES_HERMES_CONTAINER_MODEL_ENDPOINT' "$template" || {
  echo 'FAIL Hindsight compose lost the Hermes endpoint compatibility fallback'
  exit 1
}

command -v docker >/dev/null 2>&1 || { echo 'FAIL docker compose is required for route rendering'; exit 1; }
source config/versions.env
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

compose_json() {
  env -u HADES_HINDSIGHT_LLM_BASE_URL -u HADES_HINDSIGHT_LLM_MODEL \
    HADES_HINDSIGHT_IMAGE="$HADES_HINDSIGHT_IMAGE" \
    HADES_HINDSIGHT_DATA="$tmp/data" \
    HADES_HINDSIGHT_LLM_API_KEY=synthetic-hindsight-key \
    HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:18080/v1 \
    HADES_HERMES_CONTAINER_MODEL_ENDPOINT=http://host.docker.internal:18080/v1 \
    "$@" docker compose -f "$template" --project-directory "$repo_dir" config --format json
}

compose_json \
  HADES_HINDSIGHT_LLM_BASE_URL=http://host.docker.internal:19080/v1 \
  HADES_HINDSIGHT_LLM_MODEL=synthetic-extraction-model > "$tmp/override.json"
compose_json > "$tmp/fallback.json"
python3 - "$tmp/override.json" "$tmp/fallback.json" <<'PY'
import json, sys

override = json.load(open(sys.argv[1]))["services"]["hindsight"]["environment"]
fallback = json.load(open(sys.argv[2]))["services"]["hindsight"]["environment"]
assert override["HINDSIGHT_API_LLM_BASE_URL"] == "http://host.docker.internal:19080/v1", override
assert override["HINDSIGHT_API_LLM_MODEL"] == "synthetic-extraction-model", override
assert fallback["HINDSIGHT_API_LLM_BASE_URL"] == "http://host.docker.internal:18080/v1", fallback
assert fallback["HINDSIGHT_API_LLM_MODEL"] == "qwen3:14b", fallback
PY
echo 'PASS Hindsight local model route override and Hermes endpoint fallback render as configured'
