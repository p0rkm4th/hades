#!/usr/bin/env bash
set -euo pipefail
command -v curl >/dev/null 2>&1 || { echo 'FAIL curl is required'; exit 1; }
source config/versions.env
tmp=$(mktemp)
trap 'find "$tmp" -delete 2>/dev/null || true' EXIT
curl --fail --silent --show-error --location --max-time 120 --output "$tmp" "$HADES_HERMES_SOURCE_URL"
actual=$(sha256sum "$tmp" | awk '{print $1}')
[[ "$actual" == "$HADES_HERMES_SOURCE_SHA256" ]] || { echo 'FAIL public Hermes archive checksum mismatch'; exit 1; }
tar -tzf "$tmp" | grep -q '/pyproject.toml$' || { echo 'FAIL public Hermes archive has no pyproject.toml'; exit 1; }
echo "PASS public Hermes archive URL and checksum: $HADES_HERMES_SOURCE_VERSION"
