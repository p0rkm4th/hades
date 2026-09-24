#!/usr/bin/env bash
set -Eeuo pipefail

# Disposable canonical Grocy proof for the structured recipe importer. This
# never uses the live household container or credentials. The temporary
# config directory is intentionally left in /tmp for post-failure inspection.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
command -v docker >/dev/null 2>&1 || { echo 'HOST-SENSITIVE: docker is required' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo 'FAIL curl is required' >&2; exit 2; }
port=${HADES_RECIPE_GROCY_PORT:-17083}
container="hades-recipe-grocy-e2e-$$"
fixture=$(mktemp -d /tmp/hades-recipe-grocy-e2e.XXXXXX)
chmod 0777 "$fixture"
cleanup() { docker container rm --force "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" -p "127.0.0.1:${port}:80" \
  -v "$fixture:/config" -e PUID=1000 -e PGID=1000 -e TZ=America/Chicago \
  "$HADES_GROCY_IMAGE" >/dev/null

ready=0
for _ in $(seq 1 180); do
  # The first web request triggers Grocy's application/database bootstrap;
  # an unauthenticated API probe alone can return 401 against a zero-byte DB.
  curl -sS -L --max-time 2 -o /dev/null "http://127.0.0.1:${port}/" 2>/dev/null || true
  code=$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${port}/api/system/db-changed" 2>/dev/null || true)
  if [[ "$code" == 401 ]]; then ready=1; break; fi
  sleep 1
done
(( ready )) || { echo 'FAIL disposable Grocy did not become API-ready' >&2; exit 1; }

schema_ready=0
for _ in $(seq 1 90); do
  if docker exec "$container" php -r \
    '$db=new PDO("sqlite:/config/data/grocy.db"); exit((int)!$db->query("SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"api_keys\"")->fetchColumn());' \
    >/dev/null 2>&1; then
    schema_ready=1
    break
  fi
  sleep 1
done
(( schema_ready )) || { echo 'FAIL disposable Grocy schema did not finish migrating' >&2; exit 1; }
docker exec "$container" php -r \
  '$db=new PDO("sqlite:/config/data/grocy.db"); $db->exec("INSERT INTO api_keys (api_key,user_id,expires,key_type,description) VALUES (\"synthetic-recipe-e2e-key\",1,\"2999-12-31 23:59:59\",\"default\",\"disposable recipe e2e\")");'
base="http://127.0.0.1:${port}"
api=(-H 'GROCY-API-KEY: synthetic-recipe-e2e-key' -H 'Content-Type: application/json')
unit_json=$(curl -fsS "${api[@]}" "$base/api/objects/quantity_units")
unit=$(python -c 'import json,sys; print(next((x["id"] for x in json.load(sys.stdin) if x["name"] == "Cup"), ""))' <<<"$unit_json")
if [[ -z "$unit" ]]; then
  curl -fsS -X POST "${api[@]}" "$base/api/objects/quantity_units" \
    --data '{"name":"Cup","name_plural":"Cups"}' >/dev/null
  unit=$(curl -fsS "${api[@]}" "$base/api/objects/quantity_units" | \
    python -c 'import json,sys; print(next(x["id"] for x in json.load(sys.stdin) if x["name"] == "Cup"))')
fi
for product in 'Synthetic Milk Cup' 'Synthetic Eggs Cup'; do
  curl -fsS -X POST "${api[@]}" "$base/api/objects/products" \
    --data "{\"name\":\"$product\",\"location_id\":2,\"qu_id_stock\":$unit,\"qu_id_purchase\":$unit}" >/dev/null
done

BASE_URL="$base" API_KEY=synthetic-recipe-e2e-key PYTHONPATH="$repo_dir/integrations/recipe-ingest" \
python - <<'PY'
import json
import os
from urllib.request import Request, urlopen
from recipe_ingest import GrocyRecipeImporter, extract_from_html

base = os.environ["BASE_URL"]
key = os.environ["API_KEY"]
def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(base + path, data=data, method=method, headers={
        "GROCY-API-KEY": key, "Content-Type": "application/json"
    })
    with urlopen(req, timeout=10) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}

html = '''<script type="application/ld+json">{"@type":"Recipe","name":"Synthetic Breakfast","recipeYield":"2 servings","recipeIngredient":["1 cup Synthetic Milk Cup","2 cups Synthetic Eggs Cup"],"recipeInstructions":["Mix."]}</script>'''
recipe = extract_from_html(html, "https://recipes.example.test/synthetic-breakfast")
importer = GrocyRecipeImporter(request)
preview = importer.preview(recipe)
assert preview["outcome"] == "PREVIEW" and preview["plan"] and not preview["duplicate"], preview
tampered = json.loads(json.dumps(preview))
tampered["plan"]["ingredients"][0]["amount"] = "999"
assert importer.apply(tampered, confirm=True)["outcome"] == "FAILED"
assert importer.apply(preview)["outcome"] == "FAILED"
result = importer.apply(preview, confirm=True)
assert result["outcome"] == "SUCCEEDED", result
assert result["recipe"]["name"] == "Synthetic Breakfast"
assert len(result["ingredients"]) == 2
print("PASS disposable Grocy recipe preview/confirmation/read-back")
PY
