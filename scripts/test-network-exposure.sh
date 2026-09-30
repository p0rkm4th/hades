#!/usr/bin/env bash
set -Eeuo pipefail
mapfile -t compose_files < <(find deploy -type f -name '*.compose.yaml' -print | sort)
[[ ${#compose_files[@]} -gt 0 ]] || { echo 'FAIL no tracked Compose files found'; exit 1; }
for f in "${compose_files[@]}"; do
  if [[ "$f" == deploy/templates/agent-zero-operator-proxy.compose.yaml ]]; then
    nginx_template=deploy/templates/agent-zero-operator.nginx.conf.in
    grep -Fq 'network_mode: host' "$f" && grep -Fq 'user: "101:101"' "$f" && \
      grep -Fq -- '- ALL' "$f" && grep -Fq 'read_only: true' "$f" && \
      grep -Fq 'listen 127.0.0.1:@WEBUI_FRONT_PORT@' "$nginx_template" && \
      grep -Fq 'listen 127.0.0.1:@OPERATOR_FRONT_PORT@' "$nginx_template" || {
      echo "FAIL $f does not bind only unprivileged loopback gateway listeners"; exit 1;
    }
  else
    grep -Eq '127\.0\.0\.1:' "$f" || { echo "FAIL $f has no loopback-only published port"; exit 1; }
  fi
  if grep -Eq '0\.0\.0\.0:|privileged:[[:space:]]*true|/var/run/docker\.sock' "$f"; then
    echo "FAIL unsafe exposure or privilege in $f"; exit 1
  fi
done
for component in open-webui hindsight searxng; do
  grep -A 2 '^  hades-application:' "deploy/templates/$component.compose.yaml" | grep -q 'external: true' || {
    echo "FAIL $component does not attach to the installer-owned application network"; exit 1;
  }
done
grep -A 2 '^  grocy-private:' deploy/grocy.compose.yaml | grep -q 'external: true' || {
  echo 'FAIL Grocy shared network is not installer-owned'; exit 1;
}
for network in hades-application-net hades-private hades-grocy-net; do
  grep -Fq "ensure_shared_network $network" scripts/install-hades.sh || {
    echo "FAIL installer does not provision shared network $network"; exit 1;
  }
done
echo 'PASS tracked component exposure is private by default'
