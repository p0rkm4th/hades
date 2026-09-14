#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/hades-fixture"

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
echo 'PASS synthetic private fixture contract'
