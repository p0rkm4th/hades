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
grep -Fq 'HINDSIGHT_API_WORKER_ID: ${HADES_HINDSIGHT_WORKER_ID:-hades-hindsight}' "$template" || {
  echo 'FAIL Hindsight async worker must use an explicit stable identity' >&2
  exit 1
}
grep -Fq 'HINDSIGHT_API_RETAIN_MISSION: >-' "$template" || {
  echo 'FAIL Hindsight automatic retention needs the qualified durable-context mission' >&2
  exit 1
}
for policy in 'stable preferences' 'Do not infer personality' 'assistant or tool output' 'canonical sources take precedence'; do
  grep -Fqi "$policy" "$template" || {
    echo "FAIL Hindsight retain mission is missing policy text: $policy" >&2
    exit 1
  }
done
echo 'PASS Hindsight API and control-plane ports remain distinct'
echo 'PASS Hindsight async worker identity is stable across container recreation'
echo 'PASS Hindsight native retain mission is constrained to durable user context'
