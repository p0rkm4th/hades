#!/usr/bin/env bash
set -euo pipefail

# Create encrypted copies of a private recovery checkpoint. Plaintext source
# artifacts are intentionally retained until an operator verifies the
# encrypted destination and applies their own retention policy.

ROOT=${1:-}
recipient=${HADES_RECOVERY_GPG_RECIPIENT:-}
if [[ -z "$ROOT" || ! -d "$ROOT" || -z "$recipient" ]]; then
  printf 'usage: HADES_RECOVERY_GPG_RECIPIENT=RECIPIENT %s PRIVATE_RECOVERY_DIRECTORY\n' "$0" >&2
  exit 2
fi
[[ ! -L "$ROOT" ]] || { printf 'FAIL recovery root must not be a symlink\n' >&2; exit 1; }
link=$(find "$ROOT" -type l -print -quit)
[[ -z "$link" ]] || { printf 'FAIL recovery tree contains a symlink\n' >&2; exit 1; }
root_mode=$(stat -Lc '%a' "$ROOT")
case "$root_mode" in
  700|750|770|600) ;;
  *) printf 'FAIL recovery root permissions: %s\n' "$root_mode" >&2; exit 1 ;;
esac
while IFS= read -r -d '' source; do
  source_mode=$(stat -Lc '%a' "$source")
  case "$source_mode" in
    600|640|660) ;;
    *) printf 'FAIL recovery source permissions\n' >&2; exit 1 ;;
  esac
done < <(find "$ROOT" \( -path "$ROOT/encrypted-*" -o -path "$ROOT/*.failed-rehearsal" \) -prune -o -type f ! -name '*.gpg' -print0)
command -v gpg >/dev/null 2>&1 || { printf 'FAIL gpg is unavailable\n' >&2; exit 1; }

gpg --batch --with-colons --list-keys "$recipient" 2>/dev/null \
  | grep -q '^pub:' || {
    printf 'FAIL GPG recipient is not available in the configured keyring\n' >&2
    exit 1
  }

stamp=$(date +%Y%m%d-%H%M%S)
destination=$(mktemp -d "$ROOT/encrypted-${stamp}-XXXXXX")
chmod 700 "$destination"

quarantine_failed_encryption() {
  local status=$?
  if (( status != 0 )); then
    mv "$destination" "$destination.failed-rehearsal" 2>/dev/null || true
  fi
  exit "$status"
}

trap quarantine_failed_encryption EXIT

count=0
while IFS= read -r -d '' source; do
  relative=${source#"$ROOT"/}
  target="$destination/$relative.gpg"
  install -d -m 700 "$(dirname "$target")"
  gpg --batch --yes --trust-model always --output "$target" \
    --encrypt --recipient "$recipient" "$source"
  chmod 600 "$target"
  count=$((count + 1))
done < <(find "$ROOT" \
  \( -path "$ROOT/encrypted-*" -o -path "$ROOT/*.failed-rehearsal" \) -prune \
  -o -type f \
  ! -name '*.gpg' \
  ! -name '*.failed-rehearsal' \
  -print0)

if (( count == 0 )); then
  printf 'FAIL no recovery artifacts found\n' >&2
  exit 1
fi
(cd "$destination" && find . -type f -name '*.gpg' -print0 \
  | xargs -0 sha256sum | sort > SHA256SUMS)
chmod 600 "$destination/SHA256SUMS"
printf 'PASS encrypted recovery artifacts: %s\n' "$count"
printf 'PASS encrypted destination mode=%s\n' "$(stat -Lc '%a' "$destination")"
