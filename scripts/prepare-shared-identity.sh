#!/usr/bin/env bash
set -euo pipefail

# Create private LLDAP secret files without placing credentials in shell
# history, process arguments, or the repository.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
secret_dir=${HADES_IDENTITY_SECRETS_DIR:-"$HOME/.config/hades/identity-secrets"}

umask 077
mkdir -p "$secret_dir"
for name in jwt_secret key_seed admin_password; do
  if [[ -e "$secret_dir/$name" ]]; then
    echo "Refusing to overwrite existing $secret_dir/$name" >&2
    exit 1
  fi
done

openssl rand -hex 32 >"$secret_dir/jwt_secret"
openssl rand -hex 32 >"$secret_dir/key_seed"

read -r -s -p 'Choose the LLDAP admin password: ' admin_password
printf '\n'
read -r -s -p 'Repeat the LLDAP admin password: ' admin_password_again
printf '\n'
if [[ -z "$admin_password" || "$admin_password" != "$admin_password_again" ]]; then
  rm -f "$secret_dir/jwt_secret" "$secret_dir/key_seed"
  echo 'Passwords were empty or did not match; no identity secrets were kept.' >&2
  exit 1
fi
printf '%s' "$admin_password" >"$secret_dir/admin_password"
unset admin_password admin_password_again

HADES_IDENTITY_SECRETS_DIR="$secret_dir" \
  docker compose -f "$repo_dir/deploy/lldap.compose.yaml" config --quiet

echo "Identity secrets prepared in $secret_dir (mode 700/600)."
echo 'Current application authentication was not changed.'
echo "Start the staged directory with: HADES_IDENTITY_SECRETS_DIR='$secret_dir' docker compose -f '$repo_dir/deploy/lldap.compose.yaml' up -d"
