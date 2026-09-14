#!/usr/bin/env bash
set -euo pipefail

# Keep GitHub Actions dependencies immutable. Version comments may document a
# release, but execution must resolve to a full commit SHA.

workflow_root=${1:-.github/workflows}
[[ -d "$workflow_root" ]] || {
  printf 'FAIL workflow directory missing: %s\n' "$workflow_root" >&2
  exit 1
}

found=0
while IFS= read -r reference; do
  found=$((found + 1))
  ref=${reference##*@}
  if [[ ! "$ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf 'FAIL mutable workflow action reference: %s\n' "$reference" >&2
    exit 1
  fi
done < <(
  rg --no-heading --no-filename --only-matching \
    'uses:[[:space:]]*[^[:space:]#]+@[A-Za-z0-9._/-]+' \
    "$workflow_root" --glob '*.yml' --glob '*.yaml' \
    | while IFS= read -r line; do
        printf '%s\n' "${line#*uses: }"
      done
)

[[ "$found" -gt 0 ]] || {
  printf 'FAIL no workflow action references found\n' >&2
  exit 1
}
printf 'PASS workflow action references pinned: %s\n' "$found"
