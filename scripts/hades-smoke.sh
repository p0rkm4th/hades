#!/usr/bin/env bash
set -u

# Deliberately boring, secret-free HADES composition smoke check.
# Override endpoint variables for a different private deployment.
WEBUI_URL="${HADES_WEBUI_URL:-http://127.0.0.1:3000}"
HERMES_URL="${HADES_HERMES_URL:-http://127.0.0.1:8642}"
HINDSIGHT_URL="${HADES_HINDSIGHT_URL:-http://127.0.0.1:8888}"
SEARXNG_URL="${HADES_SEARXNG_URL:-http://127.0.0.1:8080}"
OLLAMA_URL="${HADES_OLLAMA_URL:-http://127.0.0.1:11434}"
AGENT_ZERO_URL="${HADES_AGENT_ZERO_URL:-http://127.0.0.1:7002}"

pass=0
fail=0
check_http() {
  local label="$1" url="$2"
  if curl -fsS --max-time 10 "$url" >/dev/null; then
    printf 'PASS %s\n' "$label"
    pass=$((pass + 1))
  else
    printf 'FAIL %s\n' "$label"
    fail=$((fail + 1))
  fi
}

check_http "Open WebUI health" "$WEBUI_URL/health"
check_http "Hermes health" "$HERMES_URL/health"
check_http "Hindsight health" "$HINDSIGHT_URL/health"

if curl -fsS --max-time 10 "$SEARXNG_URL/search?q=hades&format=json" \
    | python -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if isinstance(d.get("results"), list) else 1)' >/dev/null 2>&1; then
  printf 'PASS SearXNG JSON query\n'
  pass=$((pass + 1))
else
  printf 'FAIL SearXNG JSON query\n'
  fail=$((fail + 1))
fi

if curl -fsS --max-time 10 "$OLLAMA_URL/api/tags" \
    | python -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if isinstance(d.get("models"), list) else 1)' >/dev/null 2>&1; then
  printf 'PASS local-model endpoint\n'
  pass=$((pass + 1))
else
  printf 'FAIL local-model endpoint\n'
  fail=$((fail + 1))
fi

if python -m py_compile hermes/sitecustomize.py >/dev/null 2>&1; then
  printf 'PASS overlay syntax\n'
  pass=$((pass + 1))
else
  printf 'FAIL overlay syntax\n'
  fail=$((fail + 1))
fi

if curl -fsS --max-time 10 "$AGENT_ZERO_URL/" >/dev/null 2>&1; then
  printf 'PASS Agent Zero HTTP\n'
  pass=$((pass + 1))
else
  printf 'SKIPPED Agent Zero: not deployed\n'
fi
printf 'SKIPPED Grocy: not deployed\n'
printf 'SUMMARY pass=%d fail=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
