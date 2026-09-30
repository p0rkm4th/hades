#!/usr/bin/env bash
set -Eeuo pipefail

destination_ssh=${1:?usage: verify-destination-source.sh SSH_TARGET REPOSITORY EXPECTED_REVISION}
destination_repo=${2:?usage: verify-destination-source.sh SSH_TARGET REPOSITORY EXPECTED_REVISION}
expected_revision=${3:?usage: verify-destination-source.sh SSH_TARGET REPOSITORY EXPECTED_REVISION}

[[ "$destination_repo" == /* && "$destination_repo" != *$'\n'* ]] || {
  printf 'FAIL destination repository must be an absolute, single-line path\n' >&2
  exit 2
}
[[ "$expected_revision" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'FAIL expected destination revision must be a full commit id\n' >&2
  exit 2
}

head=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
  "test -d '$destination_repo/.git' && git -C '$destination_repo' rev-parse --verify HEAD" \
  2>/dev/null) || {
  printf 'FAIL destination repository is unavailable: %s\n' "$destination_repo" >&2
  exit 1
}
dirty=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
  "git -C '$destination_repo' status --porcelain=v1 --untracked-files=all" \
  2>/dev/null) || {
  printf 'FAIL destination repository status is unavailable: %s\n' "$destination_repo" >&2
  exit 1
}

if [[ "$head" != "$expected_revision" ]]; then
  printf 'FAIL destination revision: expected %s, got %s\n' "$expected_revision" "$head" >&2
  exit 1
fi
if [[ -n "$dirty" ]]; then
  printf 'FAIL destination checkout is dirty:\n%s\n' "$dirty" >&2
  exit 1
fi

printf 'PASS destination source revision and cleanliness: %s\n' "$expected_revision"
