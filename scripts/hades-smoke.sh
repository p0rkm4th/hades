#!/usr/bin/env bash
set -u

# Deliberately boring, secret-free HADES composition smoke check.
# Override endpoint variables for a different private deployment.
WEBUI_URL="${HADES_WEBUI_URL:-http://127.0.0.1:3000}"
LLDAP_URL="${HADES_LLDAP_URL:-http://127.0.0.1:17171}"
if [[ -n "${HADES_HERMES_URL:-}" ]]; then
  HERMES_URL="$HADES_HERMES_URL"
else
  # Production Hermes binds to the Docker host mapping rather than loopback
  # so the containerized WebUI can reach it. Discover that mapping without
  # committing a deployment-specific private address.
  hermes_host=$(docker exec hades-open-webui getent hosts host.docker.internal \
    2>/dev/null | awk 'NR == 1 { print $1 }' || true)
  HERMES_URL="http://${hermes_host:-127.0.0.1}:8642"
fi
HINDSIGHT_URL="${HADES_HINDSIGHT_URL:-http://127.0.0.1:8888}"
SEARXNG_URL="${HADES_SEARXNG_URL:-http://127.0.0.1:8080}"
OLLAMA_URL="${HADES_OLLAMA_URL:-http://127.0.0.1:11434}"
AGENT_ZERO_URL="${HADES_AGENT_ZERO_URL:-http://127.0.0.1:7002}"
GROCY_URL="${HADES_GROCY_URL:-http://127.0.0.1:7003}"

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
check_http "LLDAP health" "$LLDAP_URL/health"
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

model_ok=1
if ! curl -fsS --max-time 10 "$OLLAMA_URL/api/tags" 2>/dev/null \
    | python -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if isinstance(d.get("models"), list) else 1)' >/dev/null 2>&1; then
  # On Linux, Ollama may be bound to the Docker bridge rather than loopback.
  # Discover that gateway from Docker instead of publishing a private address
  # in this public script.
  # Resolve the exact host address visible from the production WebUI
  # container. Looking across every Docker network could find an unrelated
  # Ollama and produce a false green result.
  model_gateway=$(docker exec hades-open-webui getent hosts host.docker.internal \
    2>/dev/null | awk 'NR == 1 { print $1 }' || true)
  if [ -n "$model_gateway" ] && curl -fsS --max-time 10 "http://${model_gateway}:11434/api/tags" 2>/dev/null \
      | python -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if isinstance(d.get("models"), list) else 1)' >/dev/null 2>&1; then
    model_ok=0
  fi
else
  model_ok=0
fi
if [ "$model_ok" -eq 0 ]; then
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
if scripts/test-capability-boundary.sh >/dev/null 2>&1; then
  printf 'PASS privileged capability boundary\n'
  pass=$((pass + 1))
else
  printf 'FAIL privileged capability boundary\n'
  fail=$((fail + 1))
fi
if scripts/test-hades-memory-intent.sh >/dev/null 2>&1; then
  printf 'PASS shared-state memory boundary\n'
  pass=$((pass + 1))
else
  printf 'FAIL shared-state memory boundary\n'
  fail=$((fail + 1))
fi

if curl -fsS --max-time 10 "$AGENT_ZERO_URL/" >/dev/null 2>&1; then
  printf 'PASS Agent Zero HTTP\n'
  pass=$((pass + 1))
else
  printf 'SKIPPED Agent Zero: not deployed\n'
fi
if curl -fsS --max-time 10 "$GROCY_URL/" >/dev/null 2>&1; then
  printf 'PASS Grocy HTTP\n'
  pass=$((pass + 1))
else
  printf 'SKIPPED Grocy: not deployed\n'
fi
printf 'SUMMARY pass=%d fail=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
