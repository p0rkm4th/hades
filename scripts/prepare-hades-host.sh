#!/usr/bin/env bash
set -Eeuo pipefail

apply=0
while (($#)); do
  case "$1" in
    --apply) apply=1; shift ;;
    -h|--help)
      printf 'usage: %s [--apply]\n' "$0"
      printf 'Plan or install the bounded Fedora/Rocky HADES host prerequisites.\n'
      exit 0
      ;;
    *) printf 'FAIL unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { printf 'FAIL run as root\n' >&2; exit 1; }
[[ -r /etc/os-release ]] || { printf 'FAIL cannot read OS identification\n' >&2; exit 1; }
# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}" in
  fedora)
    [[ "${VERSION_ID:-}" == 44 ]] || {
      printf 'FAIL unsupported Fedora version: %s; use Fedora Server 44\n' "${VERSION_ID:-unknown}" >&2
      exit 1
    }
    ;;
  rocky)
    [[ "${VERSION_ID:-}" =~ ^(9|10)(\.|$) ]] || {
      printf 'FAIL unsupported Rocky version: %s; use Rocky Linux 9 or 10\n' "${VERSION_ID:-unknown}" >&2
      exit 1
    }
    ;;
  *)
    printf 'FAIL unsupported OS: %s; use Fedora Server 44 or Rocky Linux 9/10\n' "${PRETTY_NAME:-unknown}" >&2
    exit 1
    ;;
esac

packages=(git openssl)
if [[ "${ID:-}" == rocky ]]; then
  # The pinned Hermes release requires Python >=3.11. Rocky 9's default
  # python3 package is 3.9, so install the explicit compatible interpreter.
  packages+=(python3.11)
else
  packages+=(python3)
fi
printf 'HADES host prerequisite plan: %s\n' "${packages[*]}"
if (( ! apply )); then
  printf 'PLAN ONLY: rerun with --apply to install packages and enable Docker\n'
  exit 0
fi

command -v dnf >/dev/null 2>&1 || { printf 'FAIL missing dnf\n' >&2; exit 1; }
dnf install -y "${packages[@]}"
if [[ "${ID:-}" == fedora ]]; then
  dnf install -y moby-engine docker-compose
else
  # Rocky's enabled repositories do not provide the Fedora moby package
  # names. Use Docker's official CentOS-compatible RPM repository, which
  # publishes EL10 packages for the supported Rocky 10 target.
  dnf install -y dnf-plugins-core
  if [[ ! -f /etc/yum.repos.d/docker-ce.repo ]]; then
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  fi
  dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
printf 'PASS HADES host prerequisites installed and Docker enabled\n'
