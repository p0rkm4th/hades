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
command -v gpg >/dev/null 2>&1 || { printf 'FAIL gpg is unavailable\n' >&2; exit 1; }

gpg --batch --with-colons --list-keys "$recipient" 2>/dev/null \
  | grep -q '^pub:' || {
    printf 'FAIL GPG recipient is not available in the configured keyring\n' >&2
    exit 1
  }

stamp=$(date +%Y%m%d-%H%M%S)
destination=$(mktemp -d "$ROOT/encrypted-${stamp}-XXXXXX")
chmod 700 "$destination"
count=0
while IFS= read -r -d '' source; do
  relative=${source#"$ROOT"/}
  target="$destination/$relative.gpg"
  install -d -m 700 "$(dirname "$target")"
  gpg --batch --yes --trust-model always --output "$target" \
    --encrypt --recipient "$recipient" "$source"
  chmod 600 "$target"
  count=$((count + 1))
done < <(find "$ROOT" -type f \
  ! -path "$destination/*" \
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
