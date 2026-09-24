#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf 'overlay fixture\n' > "$tmp/overlay"
printf 'manifest fixture\n' > "$tmp/manifest"
python scripts/write-deployed-provenance.py \
  --output "$tmp/provenance.json" \
  --hades-sha 0123456789abcdef0123456789abcdef01234567 \
  --infra-sha fedcba9876543210fedcba9876543210fedcba98 \
  --hermes-version 0.21.2 \
  --overlay "$tmp/overlay" \
  --manifest "$tmp/manifest" \
  --deployment-path /srv/hades >/dev/null
python - "$tmp/provenance.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
assert value["schema"] == "hades/deployed-provenance/v1"
assert value["hades_sha"].startswith("0123")
assert value["infra_sha"].startswith("fedc")
assert value["hermes_version"] == "0.21.2"
assert len(value["overlay_sha256"]) == 64 and len(value["manifest_sha256"]) == 64
assert "generated_at" in value
print("PASS deployed provenance artifact is bounded, machine-readable, and hashed")
PY
