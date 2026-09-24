#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
command -v docker >/dev/null 2>&1 || { echo 'SKIP Docker unavailable'; exit 0; }

run_probe() {
  local image=$1 expected=$2 output status
  set +e
  output=$(docker run --rm --entrypoint bash -v "$repo_dir:/repo:ro" "$image" \
    -lc 'bash /repo/scripts/prepare-hades-host.sh' 2>&1)
  status=$?
  set -e
  if [[ "$expected" == supported ]]; then
    [[ $status -eq 0 ]] || { printf '%s\n' "$output"; echo "FAIL supported host classification: $image"; exit 1; }
    grep -q 'PLAN ONLY' <<<"$output" || { echo "FAIL supported host was not plan-only: $image"; exit 1; }
    echo "PASS supported host classification: $image"
  else
    [[ $status -ne 0 ]] || { printf '%s\n' "$output"; echo "FAIL unsupported host accepted: $image"; exit 1; }
    grep -q 'unsupported OS' <<<"$output" || { printf '%s\n' "$output"; echo "FAIL unsupported-host guidance missing: $image"; exit 1; }
    echo "PASS unsupported host fails closed: $image"
  fi
}

run_probe fedora:44 supported
run_probe rockylinux:9 supported
run_probe ubuntu:24.04 unsupported
run_probe debian:stable-slim unsupported
run_probe archlinux:latest unsupported
run_probe opensuse/tumbleweed:latest unsupported
echo 'PASS host OS detection matrix (classification only; not a full clean install)'
