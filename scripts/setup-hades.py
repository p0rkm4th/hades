#!/usr/bin/env python3
"""Product-level HADES setup: collect a few decisions, then use tracked tools."""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


def run(args: list[str], cwd: Path, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True,
                            capture_output=capture)
    return result.stdout if capture else ""


def secret() -> str:
    return secrets.token_hex(32)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and install a fresh HADES instance")
    parser.add_argument("--output", type=Path, default=Path("/etc/hades"))
    parser.add_argument("--profile", choices=("standalone", "cpu-only"), default="standalone")
    parser.add_argument("--exposure", choices=("local", "lan"), default="local")
    parser.add_argument("--owner-id", default="admin")
    parser.add_argument("--model-endpoint", default=os.environ.get("HADES_MODEL_ENDPOINT", "http://127.0.0.1:11434/v1"))
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.output.is_symlink() or not args.output.is_absolute() or args.output == Path("/"):
        raise SystemExit("FAIL --output must be an absolute non-root regular directory path")
    if not args.owner_id.replace("_", "a").replace("-", "a").replace(".", "a").isalnum():
        raise SystemExit("FAIL --owner-id contains unsupported characters")
    if not (args.model_endpoint.startswith("http://") or args.model_endpoint.startswith("https://")):
        raise SystemExit("FAIL --model-endpoint must be an http(s) URL")
    if args.output.exists():
        raise SystemExit(f"FAIL setup output already exists: {args.output}; use repair or reconfigure")
    if args.test_mode:
        print(f"PLAN profile={args.profile} exposure={args.exposure} owner={args.owner_id} model_endpoint=configured")
        print("PLAN generate fresh identity, build pinned artifacts, render records, and invoke the bounded installer")
        return 0
    if os.geteuid() != 0:
        raise SystemExit("FAIL setup requires root for host/runtime installation; use --test-mode to inspect the plan")
    for command in ("docker", "openssl", "curl", "python3", "groupadd", "useradd"):
        if shutil.which(command) is None:
            raise SystemExit(f"FAIL missing prerequisite: {command}")
    if not args.yes and sys.stdin.isatty():
        print(f"Fresh HADES setup: profile={args.profile}, exposure={args.exposure}, owner={args.owner_id}")
        if input("Continue? [y/N] ").strip().lower() != "y":
            print("Setup cancelled; nothing changed")
            return 0

    if shutil.which("getent") is None:
        raise SystemExit("FAIL missing prerequisite: getent")
    if subprocess.run(["getent", "group", "hades-runtime"], check=False,
                      stdout=subprocess.DEVNULL).returncode != 0:
        run(["groupadd", "--system", "hades-runtime"], repo)
    if subprocess.run(["id", "-u", "hades-runtime"], check=False,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        run(["useradd", "--system", "--gid", "hades-runtime", "--home-dir",
             "/var/lib/hades", "--shell", "/usr/sbin/nologin", "hades-runtime"], repo)

    output = args.output
    (output / "secrets/identity").mkdir(parents=True, mode=0o700)
    for relative in ("secrets/grocy", "secrets/agent-zero", "secrets/searxng",
                     "profile/profiles/hades", "state", "backups", "config"):
        (output / relative).mkdir(parents=True, mode=0o750)
    identity = {name: secret() for name in ("jwt_secret", "key_seed", "admin_password")}
    for name, value in identity.items():
        path = output / "secrets/identity" / name
        path.write_text(value + "\n")
        path.chmod(0o600)
    values = {name: secret() for name in ("hermes", "hindsight", "grocy", "agent", "searx")}
    for directory, name in (("grocy", "grocy"), ("agent-zero", "agent"), ("searxng", "searx")):
        path = output / "secrets" / directory / ("secret_key" if name == "searx" else "api_key" if name == "grocy" else "credential")
        path.write_text(values[name] + "\n")
        path.chmod(0o600)

    image_output = run(["bash", str(repo / "scripts/build-open-webui-artifact.sh"),
                        f"hades-open-webui:{args.profile}"], repo, capture=True)
    image = next((line.split("=", 1)[1] for line in image_output.splitlines()
                  if line.startswith("HADES_OPEN_WEBUI_IMAGE=")), "")
    if not image:
        raise SystemExit("FAIL Open WebUI artifact builder returned no immutable image reference")
    run(["bash", str(repo / "scripts/install-hermes-artifact.sh"), "--prefix", "/opt/hades-hermes"], repo)
    docker_gateway = "172.17.0.1"
    ip = shutil.which("ip")
    if ip:
        probe = subprocess.run([ip, "-4", "addr", "show", "docker0"], text=True,
                               capture_output=True, check=False).stdout
        for token in probe.split():
            if "/" in token and token[0].isdigit():
                docker_gateway = token.split("/", 1)[0]
                break
    container_model = args.model_endpoint.replace("127.0.0.1", "host.docker.internal")
    bind = "127.0.0.1:3000" if args.exposure == "local" else "0.0.0.0:3000"
    config = (repo / "hermes/config.yaml.example").read_text()
    config = config.replace("http://model-server.local:11434/v1", args.model_endpoint)
    config = config.replace("default: qwen3.6:35b", "default: qwen3:8b")
    for config_path in (output / "profile/config.yaml",
                        output / "profile/profiles/hades/config.yaml"):
        config_path.write_text(config)
        config_path.chmod(0o600)
    (output / "profile/hermes.env").write_text(
        f"API_SERVER_ENABLED=true\nAPI_SERVER_HOST={docker_gateway}\nAPI_SERVER_PORT=8642\n"
        f"API_SERVER_KEY={values['hermes']}\nAPI_SERVER_MODEL_NAME=hermes-agent\nHERMES_MAX_ITERATIONS=12\n")
    (output / "profile/hermes.env").chmod(0o600)
    env = {
        "HADES_INPUTS_VERSION": "2", "HADES_PROFILE": args.profile,
        "HADES_INFRA_COMMIT": "unknown", "HADES_DEPLOYMENT_ID": f"hades-{secret()[:12]}",
        "HADES_PROVENANCE_FILE": str(output / "provenance.json"),
        "HADES_STATE_ROOT": str(output / "state"), "HADES_CONFIG_ROOT": str(output / "config"),
        "HADES_BACKUP_ROOT": str(output / "backups"), "HADES_IDENTITY_SECRETS_DIR": str(output / "secrets/identity"),
        "HADES_OPEN_WEBUI_IMAGE": image, "HADES_OPEN_WEBUI_DATA": str(output / "state/open-webui"),
        "HADES_HINDSIGHT_DATA": str(output / "state/hindsight"), "HADES_SEARXNG_DATA": str(output / "state/searxng"),
        "HADES_SEARXNG_SECRET_FILE": str(output / "secrets/searxng/secret_key"),
        "HADES_HINDSIGHT_LLM_API_KEY": values["hindsight"],
        "HADES_HERMES_API_BASE_URL": "http://127.0.0.1:8642/v1",
        "HADES_HERMES_CONTAINER_API_BASE_URL": "http://host.docker.internal:8642/v1",
        "HADES_HERMES_API_BIND_HOST": docker_gateway, "HADES_HERMES_MODEL_ENDPOINT": args.model_endpoint,
        "HADES_HERMES_CONTAINER_MODEL_ENDPOINT": container_model,
        "HADES_HERMES_WORKING_DIRECTORY": str(repo), "HADES_HERMES_EXECUTABLE": "/opt/hades-hermes/bin/hermes",
        "HADES_HERMES_RUNTIME_USER": "hades-runtime", "HADES_HERMES_RUNTIME_GROUP": "hades-runtime",
        "HADES_HERMES_PROFILE": str(output / "profile"), "HADES_HERMES_API_KEY": values["hermes"],
        "HADES_OPEN_WEBUI_BIND": bind, "HADES_OPEN_WEBUI_LDAP_APP_PASSWORD": identity["admin_password"],
        "HADES_GROCY_API_KEY_FILE": str(output / "secrets/grocy/api_key"),
        "HADES_AGENT_ZERO_CREDENTIAL_FILE": str(output / "secrets/agent-zero/credential"),
        "HADES_OWNER_BOOTSTRAP_ID": args.owner_id, "HADES_OWNER_SUBJECT_IDS": args.owner_id,
    }
    operator = output / "operator-inputs.env"
    operator.write_text("\n".join(f"{key}={value}" for key, value in env.items()) + "\n")
    operator.chmod(0o600)
    run(["bash", str(repo / "scripts/render-deployment-records.sh"), str(operator),
         str(output / "config/private-deployment")], repo)
    run(["bash", str(repo / "scripts/install-hades.sh"), "--inputs", str(operator), "--preflight"], repo)
    run(["bash", str(repo / "scripts/install-hades.sh"), "--inputs", str(operator)], repo)
    print("HADES is ready.")
    print("Open: http://127.0.0.1:3000" if args.exposure == "local" else "Open: http://<this-machine>:3000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
