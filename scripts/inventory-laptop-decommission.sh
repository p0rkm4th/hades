#!/usr/bin/env bash
set -euo pipefail

# Read-only inventory for the post-cutover laptop cleanup review.
# This script deliberately does not stop, remove, prune, or alter anything.

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
infra_repo_dir=$(cd "$repo_dir/../hades-infra" 2>/dev/null && pwd || true)
phase=${1:-before}
case "$phase" in
  before|after) ;;
  *) printf 'usage: %s [before|after]\n' "$0" >&2; exit 2 ;;
esac

production_containers=(
  hades-open-webui
  hades-hindsight
  hades-grocy
  hades-agent-zero
  hades-searxng
  hades-lldap-production
)

printf '%s\n' 'HADES laptop decommission inventory (read-only)'
printf 'timestamp_utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'host\t%s\n' "$(hostname --fqdn 2>/dev/null || hostname)"
printf 'phase\t%s\n' "$phase"
printf 'scope\tproduction runtime candidates only; no mutation performed\n'

printf '\n%s\n' '[disk]'
df -hP /home | awk 'NR == 1 || !seen[$1]++'
if [[ -d /var/lib/docker ]]; then
  df -hP /var/lib/docker | awk 'NR > 1'
fi

printf '\n%s\n' '[hermes-user-service]'
for state in is-enabled is-active; do
  if command -v systemctl >/dev/null 2>&1; then
    result=$(systemctl --user "$state" hades-hermes.service 2>&1 || true)
    printf '%s\t%s\n' "$state" "$result"
  else
    printf '%s\tnot-available\n' "$state"
  fi
done

printf '\n%s\n' '[production-containers]'
if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'docker\tnot-available'
else
  for name in "${production_containers[@]}"; do
    if docker container inspect "$name" >/dev/null 2>&1; then
      docker container inspect --format '{{.Name}}\t{{.State.Status}}\t{{.Config.Image}}\t{{.HostConfig.RestartPolicy.Name}}' "$name" \
        | sed 's#^/##'
    else
      printf '%s\tnot-found\n' "$name"
    fi
  done
fi

printf '\n%s\n' '[docker-accounting]'
if command -v docker >/dev/null 2>&1; then
  docker system df 2>&1 || printf '%s\n' 'docker system accounting unavailable'
else
  printf '%s\n' 'docker\tnot-available'
fi

printf '\n%s\n' '[classification]'
printf '%s\t%s\n' 'candidate-after-owner-cutover' "${production_containers[*]} + user-level hades-hermes.service"
printf '%s\t%s\n' 'preserve' "$repo_dir ${infra_repo_dir:-<infra-repository>} SSH/Tailscale/admin tooling /var/lib/hades /var/backups/hades"
printf '%s\t%s\n' 'review-required' 'all other containers, volumes, images, model files, caches, staging assets, and personal files'
printf '%s\n' 'No cleanup is authorized by this inventory; review the migration allowlist and rollback verification first.'
