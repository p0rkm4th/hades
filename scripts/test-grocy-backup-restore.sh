#!/usr/bin/env bash
set -Eeuo pipefail

# Restore one canonical Grocy SQLite backup into a fresh, network-isolated
# pinned container, then verify the restored marker through Grocy's API.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
image=${1:-$HADES_GROCY_IMAGE}
backup=${2:-}
key_file=${3:-}

fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
[[ "$image" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || fail 'Grocy image must be pinned by digest'
[[ -n "$backup" && -f "$backup" && ! -L "$backup" && -s "$backup" ]] ||
  fail 'provide a nonempty regular Grocy SQLite backup'
[[ -n "$key_file" && -f "$key_file" && ! -L "$key_file" ]] ||
  fail 'provide the protected API key for the synthetic restored database'
key_mode=$(stat -Lc '%a' "$key_file")
case "$key_mode" in 600|640) ;; *) fail 'Grocy API key file must have mode 0600 or 0640';; esac
command -v docker >/dev/null 2>&1 || fail 'docker is required'
docker image inspect "$image" >/dev/null 2>&1 || fail 'pinned Grocy image is not available locally'

suffix="$(date -u +%Y%m%d%H%M%S)-${RANDOM}-${BASHPID}"
container="hades-grocy-restore-test-${suffix}"
volume="hades-grocy-restore-test-${suffix}"
volume_created=0
container_created=0
cleanup() {
  if ((container_created)); then docker rm -f "$container" >/dev/null 2>&1 || true; fi
  if ((volume_created)); then docker volume rm "$volume" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

docker volume create "$volume" >/dev/null
volume_created=1
docker run --rm --network none -v "$volume:/config" --entrypoint /bin/sh \
  "$image" -c 'mkdir -p /config/data'
docker create --name "$container" --network none -v "$volume:/config" \
  -e PUID=1000 -e PGID=1000 -e TZ=America/Chicago "$image" >/dev/null
container_created=1
docker cp "$backup" "$container:/config/data/grocy.db"
docker run --rm --network none -v "$volume:/config" --entrypoint /bin/sh \
  "$image" -c 'rm -f /config/data/grocy.db-wal /config/data/grocy.db-shm; chown 1000:1000 /config/data/grocy.db; chmod 600 /config/data/grocy.db'
docker start "$container" >/dev/null

ready=0
for _ in $(seq 1 90); do
  [[ "$(docker inspect --format '{{.State.Status}}' "$container")" == running ]] || break
  result=$(docker exec -i "$container" php -r '
$key=trim(stream_get_contents(STDIN));
$ctx=stream_context_create(["http"=>["timeout"=>2,"ignore_errors"=>true,"header"=>"GROCY-API-KEY: ".$key."\r\n"]]);
$raw=@file_get_contents("http://127.0.0.1/api/objects/shopping_list", false, $ctx);
if ($raw === false) exit(1);
$rows=json_decode($raw,true); if (!is_array($rows)) exit(2);
foreach ($rows as $row) {
  $id=$row["product_id"] ?? null; if (!$id) continue;
  $productRaw=@file_get_contents("http://127.0.0.1/api/objects/products/".$id, false, $ctx);
  $product=json_decode((string)$productRaw,true);
  if (($product["name"] ?? "") === "HADES Synthetic Milk" && (float)($row["amount"] ?? 0) === 1.0) {
    echo "PASS restored Grocy API returned the canonical synthetic shopping-list marker\n"; exit(0);
  }
}
exit(3);
' < "$key_file" 2>/dev/null) && {
    printf '%s\n' "$result"
    ready=1
    break
  }
  sleep 2
done
((ready)) || fail 'restored Grocy did not return the canonical synthetic marker'
