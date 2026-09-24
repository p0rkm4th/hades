#!/usr/bin/env bash
set -euo pipefail

template='deploy/templates/hindsight.compose.yaml'
grep -Fq 'HINDSIGHT_API_PORT: "8888"' "$template" || {
  echo 'FAIL Hindsight API must use the image API port 8888' >&2
  exit 1
}
grep -Fq 'HADES_HINDSIGHT_CONTROL_PORT:-9999' "$template" || {
  echo 'FAIL Hindsight control-plane port mapping is missing' >&2
  exit 1
}
if grep -Fq 'HINDSIGHT_API_PORT: "9999"' "$template"; then
  echo 'FAIL Hindsight API and control-plane ports collide' >&2
  exit 1
fi
echo 'PASS Hindsight API and control-plane ports remain distinct'
