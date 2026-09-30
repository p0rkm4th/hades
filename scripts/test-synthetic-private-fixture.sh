#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ -x "$repo_dir/scripts/create-synthetic-private-fixture.sh" ]] || { echo 'FAIL fixture generator is not executable'; exit 1; }
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/hades-fixture"
sandbox="$fixture/sandbox"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env"
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env"
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env"

config_root=$(awk -F= '$1 == "HADES_CONFIG_ROOT" {print $2}' "$fixture/hades-fixture/operator.env")
missing_asset="$sandbox${config_root}/assets/finance-upload.js"
asset_hold="$fixture/finance-upload.js.saved"
[[ -f "$missing_asset" ]] || { echo 'FAIL installer omitted the finance upload asset'; exit 1; }
mv -- "$missing_asset" "$asset_hold"
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env" >"$fixture/missing-asset-doctor.log" 2>&1; then
  echo 'FAIL doctor accepted an installation missing a Compose-mounted finance asset'; exit 1
fi
grep -Fq 'FAIL HADES layer missing: assets/finance-upload.js' "$fixture/missing-asset-doctor.log" || {
  cat "$fixture/missing-asset-doctor.log" >&2
  echo 'FAIL doctor did not identify the missing finance upload asset'; exit 1
}
mv -- "$asset_hold" "$missing_asset"
echo 'PASS doctor rejects a missing Open WebUI Compose-mounted asset'

hermes_profile=$(awk -F= '$1 == "HADES_HERMES_PROFILE" {print $2}' "$fixture/hades-fixture/operator.env")
profile="$sandbox${hermes_profile}/config.yaml"
profile_hold="$fixture/hermes-config.yaml.saved"
cp -- "$profile" "$profile_hold"
python3 - "$profile" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
start = text.index('  grocy_recipe_authoring:\n')
end = text.index('  hades-agent-zero:\n', start)
path.write_text(text[:start] + text[end:], encoding='utf-8')
PY
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env" >"$fixture/missing-grocy-adapter-doctor.log" 2>&1; then
  echo 'FAIL doctor accepted a profile missing the required recipe-authoring adapter'; exit 1
fi
grep -Fq 'FAIL Hermes profile is missing a required V1 registration or profile classification' "$fixture/missing-grocy-adapter-doctor.log" || {
  cat "$fixture/missing-grocy-adapter-doctor.log" >&2
  echo 'FAIL doctor did not identify the missing recipe-authoring adapter'; exit 1
}
mv -- "$profile_hold" "$profile"
echo 'PASS doctor rejects a missing required Grocy recipe-authoring registration'

profile_hold="$fixture/hermes-config.yaml.recipe-ingest-saved"
cp -- "$profile" "$profile_hold"
python3 - "$profile" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
start = text.index('  recipe-url-ingest:\n')
end = text.index('  receipt-ocr-gateway:\n', start)
path.write_text(text[:start] + text[end:], encoding='utf-8')
PY
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env" >"$fixture/missing-recipe-ingest-doctor.log" 2>&1; then
  echo 'FAIL doctor accepted a profile missing V1 recipe URL ingestion'; exit 1
fi
grep -Fq 'FAIL Hermes profile is missing a required V1 registration or profile classification' "$fixture/missing-recipe-ingest-doctor.log" || {
  cat "$fixture/missing-recipe-ingest-doctor.log" >&2
  echo 'FAIL doctor did not identify the missing V1 recipe URL registration'; exit 1
}
mv -- "$profile_hold" "$profile"
echo 'PASS doctor rejects a missing V1 recipe URL registration'

profile_hold="$fixture/hermes-config.yaml.owner-gated-saved"
cp -- "$profile" "$profile_hold"
python3 - "$profile" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
marker = '  finance-file-import:\n    # Enable only after the owner approves the private file-intake path.\n    enabled: false\n'
if text.count(marker) != 1:
    raise SystemExit('expected exactly one canonical finance-file-import disabled marker')
path.write_text(text.replace(marker, marker.replace('enabled: false', 'enabled: true'), 1), encoding='utf-8')
PY
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$fixture/hades-fixture/operator.env" >"$fixture/enabled-owner-gate-doctor.log" 2>&1 || {
  cat "$fixture/enabled-owner-gate-doctor.log" >&2
  echo 'FAIL doctor rejected an operator profile solely because an owner-gated server is enabled'; exit 1
}
grep -Fq 'WARN owner-gated Hermes MCP is enabled in operator profile: finance-file-import; explicit owner activation must be verified' "$fixture/enabled-owner-gate-doctor.log" || {
  cat "$fixture/enabled-owner-gate-doctor.log" >&2
  echo 'FAIL doctor did not expose the enabled owner-gated server warning'; exit 1
}
mv -- "$profile_hold" "$profile"
echo 'PASS doctor warns when an operator profile enables an owner-gated Hermes server'

input="$fixture/hades-fixture/operator.env"
[[ $(stat -c '%a' "$input") == 600 ]] || { echo 'FAIL synthetic operator input permissions'; exit 1; }
for path in \
  "$fixture/hades-fixture/records/open-webui.compose.yaml" \
  "$fixture/hades-fixture/records/hindsight.compose.yaml" \
  "$fixture/hades-fixture/records/searxng.compose.yaml" \
  "$fixture/hades-fixture/records/hermes.service"; do
  [[ $(stat -c '%a' "$path") == 600 ]] || { echo "FAIL synthetic private record permissions: $path"; exit 1; }
done
docker compose -f "$fixture/hades-fixture/records/open-webui.compose.yaml" config --quiet
docker compose -f "$fixture/hades-fixture/records/hindsight.compose.yaml" config --quiet
docker compose -f "$fixture/hades-fixture/records/searxng.compose.yaml" config --quiet
grep -q '^name: hades-synthetic-open-webui$' "$fixture/hades-fixture/records/open-webui.compose.yaml"
grep -q '^name: hades-synthetic-hindsight$' "$fixture/hades-fixture/records/hindsight.compose.yaml"
grep -q '^name: hades-synthetic-searxng$' "$fixture/hades-fixture/records/searxng.compose.yaml"
grep -q '^    restart: unless-stopped$' "$fixture/hades-fixture/records/open-webui.compose.yaml"
grep -q '^    restart: unless-stopped$' "$fixture/hades-fixture/records/hindsight.compose.yaml"
grep -q '^    restart: unless-stopped$' "$fixture/hades-fixture/records/searxng.compose.yaml"
if grep -Eq 'image: [^@[:space:]]+:[^@[:space:]]+$' "$fixture/hades-fixture/records"/*.compose.yaml; then
  echo 'FAIL synthetic private fixture emitted a mutable image'; exit 1
fi
source config/versions.env
grep -Fq "image: $HADES_HINDSIGHT_IMAGE" "$fixture/hades-fixture/records/hindsight.compose.yaml"
grep -Fq "image: $HADES_SEARXNG_IMAGE_RECORD" "$fixture/hades-fixture/records/searxng.compose.yaml"
# Keep host-local, potentially unreadable service units out of this disposable
# syntax check; only vendor dependencies are needed for validation.
SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system \
  systemd-analyze verify "$fixture/hades-fixture/records/hermes.service"
for secret in jwt_secret key_seed admin_password; do
  [[ $(stat -c '%a' "$fixture/hades-fixture/identity/$secret") == 600 ]] || {
    echo "FAIL synthetic identity secret permissions: $secret"; exit 1;
  }
done
for secret in hindsight-secret grocy-api-key agent-zero-credential; do
  [[ $(stat -c '%a' "$fixture/hades-fixture/$secret") == 600 ]] || {
    echo "FAIL synthetic secret permissions: $secret"; exit 1;
  }
done
grep -Fqx 'REQUIRED_GROCY_UI_API_KEY' "$fixture/hades-fixture/grocy-api-key"
echo 'PASS synthetic private fixture contract'
