#!/usr/bin/env bash
set -Eeuo pipefail

apply=0
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
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
source "$repo_dir/config/versions.env"
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

packages=(git openssl acl)
if [[ "${ID:-}" == fedora ]]; then
  packages+=(moby-engine docker-compose python3.13)
else
  packages+=(dnf-plugins-core epel-release python3.13 docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)
  printf 'Host repository setup: enable CRB and EPEL; add Docker CE CentOS-compatible repository if missing\n'
fi
printf 'HADES host prerequisite plan: %s\n' "${packages[*]}"
printf 'Pinned Hermes build tools: Python 3.13 and uv %s at /opt/hades-hermes-tools/uv-%s\n' "$HADES_HERMES_UV_VERSION" "$HADES_HERMES_UV_VERSION"
if (( ! apply )); then
  printf 'PLAN ONLY: rerun with --apply to install packages and enable Docker\n'
  exit 0
fi

command -v dnf >/dev/null 2>&1 || { printf 'FAIL missing dnf\n' >&2; exit 1; }
dnf install -y git openssl acl
if [[ "${ID:-}" == fedora ]]; then
  dnf install -y moby-engine docker-compose python3.13
else
  # Rocky's enabled repositories do not provide the Fedora moby package
  # names. Use Docker's official CentOS-compatible RPM repository, which
  # publishes EL10 packages for the supported Rocky 10 target.
  dnf install -y dnf-plugins-core
  if [[ ! -f /etc/yum.repos.d/docker-ce.repo ]]; then
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  fi
  dnf config-manager --set-enabled crb
  dnf install -y epel-release
  dnf install -y python3.13
  dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
tools_root=/opt/hades-hermes-tools
uv_prefix="$tools_root/uv-$HADES_HERMES_UV_VERSION"
if [[ -x "$uv_prefix/bin/uv" ]]; then
  [[ "$("$uv_prefix/bin/uv" --version | awk '{print $1 " " $2}')" == "uv $HADES_HERMES_UV_VERSION" ]] || {
    printf 'FAIL existing Hermes build-tool pin is invalid: %s\n' "$uv_prefix" >&2; exit 1;
  }
else
  [[ ! -e "$uv_prefix" ]] || { printf 'FAIL incomplete Hermes build-tool path exists: %s\n' "$uv_prefix" >&2; exit 1; }
  install -d -m 0755 "$tools_root"
  created_uv_prefix=1
  cleanup_uv_prefix() {
    status=$?
    if (( status != 0 )) && (( created_uv_prefix )); then rm -rf -- "$uv_prefix"; fi
    return "$status"
  }
  trap cleanup_uv_prefix EXIT
  python3.13 -m venv "$uv_prefix"
  "$uv_prefix/bin/python" -m pip install --disable-pip-version-check --no-input --no-deps "uv==$HADES_HERMES_UV_VERSION"
  [[ "$("$uv_prefix/bin/uv" --version | awk '{print $1 " " $2}')" == "uv $HADES_HERMES_UV_VERSION" ]] || {
    printf 'FAIL installed uv does not match the pinned build-tool version\n' >&2; exit 1;
  }
  created_uv_prefix=0
  trap - EXIT
fi
systemctl enable --now docker
printf 'PASS HADES host prerequisites installed and Docker enabled\n'
