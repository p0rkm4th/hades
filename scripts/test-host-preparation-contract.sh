#!/usr/bin/env bash
set -Eeuo pipefail

script=scripts/prepare-hades-host.sh
[[ -x "$script" ]] || { printf 'FAIL host preparation helper is not executable\n' >&2; exit 1; }
bash -n "$script"
grep -q 'fedora' "$script"
grep -q 'rocky' "$script"
grep -q 'moby-engine docker-compose git openssl' "$script"
grep -q -- '--apply' "$script"
grep -q 'systemctl enable --now docker' "$script"
printf 'PASS bounded Fedora/Rocky host preparation contract\n'
