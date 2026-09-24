#!/usr/bin/env bash
set -euo pipefail

# Opt-in network acceptance for a representative public recipe page. This is
# separate from offline CI because publishers can change or block access.
url="${1:-https://www.kingarthurbaking.com/recipes/banana-bread-recipe}"
PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/recipe-ingest" && pwd)" \
  RECIPE_URL="$url" python3 - <<'PY'
import os
from recipe_ingest import extract_from_url

url = os.environ["RECIPE_URL"]
result = extract_from_url(url)
assert result["source_url"] == url
assert result["title"].strip()
assert result["ingredients"]
assert result["instructions"]
print("PASS public recipe URL produced a bounded preview")
print("title=", result["title"])
print("ingredients=", len(result["ingredients"]))
print("instructions=", len(result["instructions"]))
print("requires_review=", result["requires_review"])
PY
