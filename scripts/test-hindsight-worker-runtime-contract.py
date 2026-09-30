#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

from hindsight_runtime_contract import worker_identity_matches

repo = Path(__file__).resolve().parents[1]
for script in (repo / "scripts/hades-doctor.sh", repo / "scripts/validate-install.sh"):
    source = script.read_text(encoding="utf-8")
    assert 'if [[ -n "${HADES_HINDSIGHT_COMPOSE_FILE:-}" ]]; then' in source, script
    assert 'scripts/check-hindsight-worker-runtime.py' in source, script

compose = {"services": {"hindsight": {"environment": {"HINDSIGHT_API_WORKER_ID": "hades-hindsight"}}}}
running = {"Config": {"Env": ["PATH=/usr/bin", "HINDSIGHT_API_WORKER_ID=hades-hindsight"]}}
assert worker_identity_matches(compose, running)
assert not worker_identity_matches(compose, {"Config": {"Env": ["PATH=/usr/bin"]}})
assert not worker_identity_matches(compose, {"Config": {"Env": ["HINDSIGHT_API_WORKER_ID=ephemeral-container-id"]}})
assert not worker_identity_matches({"services": {"hindsight": {"environment": {}}}}, running)

with tempfile.TemporaryDirectory(prefix="hades-hindsight-worker-check-") as tmp:
    root = Path(tmp)
    fake_bin = root / "bin"
    fake_bin.mkdir()
    compose_file = root / "hindsight.compose.yaml"
    compose_file.write_text("services: {}\n")
    env_file = root / "operator.env"
    env_file.write_text("fixture only\n")
    compose_json = root / "compose.json"
    compose_json.write_text(json.dumps(compose))
    inspect_json = root / "inspect.json"
    inspect_json.write_text(json.dumps([running]))
    docker = fake_bin / "docker"
    docker.write_text("""#!/usr/bin/env python3
import os,sys
path=os.environ['HADES_TEST_COMPOSE'] if sys.argv[1]=='compose' else os.environ['HADES_TEST_INSPECT']
print(open(path,encoding='utf-8').read())
""")
    docker.chmod(0o700)
    env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
               HADES_TEST_COMPOSE=str(compose_json), HADES_TEST_INSPECT=str(inspect_json))
    helper = Path(__file__).with_name("check-hindsight-worker-runtime.py")
    command = ["python3", str(helper), "--compose-file", str(compose_file), "--env-file", str(env_file)]
    passed = subprocess.run(command, env=env, text=True, capture_output=True)
    assert passed.returncode == 0 and "PASS Hindsight worker identity" in passed.stdout, passed
    inspect_json.write_text(json.dumps([{"Config": {"Env": ["PATH=/usr/bin"]}}]))
    failed = subprocess.run(command, env=env, text=True, capture_output=True)
    assert failed.returncode != 0 and "FAIL Hindsight worker identity" in failed.stdout, failed
    assert "hades-hindsight" not in failed.stdout

    fixture = root / "legacy-v1-fixture"
    subprocess.run(
        ["bash", str(repo / "scripts/create-synthetic-private-fixture.sh"), str(fixture)],
        check=True, text=True, capture_output=True,
    )
    operator_file = fixture / "operator.env"
    operator = operator_file.read_text(encoding="utf-8")
    hermes = fake_bin / "hermes"
    manifest = (repo / "config/versions.env").read_text(encoding="utf-8")
    import re
    version = re.search(r"^HADES_HERMES_VERSION=(.+)$", manifest, re.MULTILINE).group(1).strip("'\"")
    hermes.write_text(f"#!/bin/sh\nprintf 'Hermes Agent {version}\\n'\n", encoding="utf-8")
    hermes.chmod(0o700)
    operator = operator.replace("HADES_HERMES_EXECUTABLE=/usr/bin/hermes", f"HADES_HERMES_EXECUTABLE={hermes}")
    operator_file.write_text(operator, encoding="utf-8")
    operator_file.chmod(0o600)
    profile = fixture / "profile"
    (profile / "hermes.env").write_text("synthetic only\n", encoding="utf-8")
    contract = json.loads((repo / "config/reconstruction-manifest.json").read_text(encoding="utf-8"))["hermes_profile_contract"]
    profile_config = ["mcp_servers:"]
    for name, markers in contract["v1_required_servers"].items():
        profile_config.extend([f"  {name}:", "    command: python3"])
        profile_config.extend(f"    # {marker}" for marker in markers)
    (profile / "config.yaml").write_text("\n".join(profile_config) + "\n", encoding="utf-8")
    for name in ("hermes.env", "config.yaml"):
        (profile / name).chmod(0o600)
    (fixture / "records/hindsight.compose.yaml").write_text(
        "services:\n  hindsight:\n    environment:\n      HINDSIGHT_API_WORKER_ID: hades-hindsight\n",
        encoding="utf-8",
    )
    (fixture / "records/hindsight.compose.yaml").chmod(0o600)
    client_auth = fixture / "records/agent-zero-client-auth.env"
    client_auth.write_text("AGENT_ZERO_API_KEY=synthetic-agent-zero-credential\n", encoding="utf-8")
    client_auth.chmod(0o600)
    compose_json.write_text(json.dumps(compose), encoding="utf-8")
    inspect_json.write_text(json.dumps([running]), encoding="utf-8")

    docker.write_text("""#!/usr/bin/env python3
import json,os,sys
args=sys.argv[1:]
if args[:1]==['compose']:
    if 'version' in args: print('Docker Compose synthetic')
    elif '--format' in args: print(open(os.environ['HADES_TEST_COMPOSE'],encoding='utf-8').read())
elif args[:1]==['network']:
    print('bridge local')
elif args[:1]==['inspect']:
    if len(args)==2 and args[1]=='hades-hindsight':
        print(open(os.environ['HADES_TEST_INSPECT'],encoding='utf-8').read())
    elif '-f' in args:
        template=args[args.index('-f')+1]
        print('healthy' if 'Health' in template else 'running')
elif args[:1]==['info']:
    pass
""", encoding="utf-8")
    docker.chmod(0o700)
    fake_commands = {
        "systemctl": "#!/bin/sh\necho active\n",
        "id": "#!/bin/sh\necho hades-runtime\n",
        "runuser": "#!/bin/sh\nexit 0\n",
    }
    for name, contents in fake_commands.items():
        path = fake_bin / name
        path.write_text(contents, encoding="utf-8")
        path.chmod(0o700)
    doctor_env = dict(
        env,
        PATH=f"{fake_bin}:{os.environ['PATH']}",
        HADES_TEST_COMPOSE=str(compose_json),
        HADES_TEST_INSPECT=str(inspect_json),
    )
    doctor = repo / "scripts/hades-doctor.sh"
    command = ["bash", str(doctor), "--inputs", str(operator_file), "--test-mode"]
    legacy_pass = subprocess.run(command, env=doctor_env, text=True, capture_output=True)
    assert legacy_pass.returncode == 0, legacy_pass.stdout + legacy_pass.stderr
    assert "PASS required and classified Hermes MCP profile contract" in legacy_pass.stdout
    assert "PASS read-only synthetic doctor" in legacy_pass.stdout
    assert "container runtime available" not in legacy_pass.stdout
print("PASS legacy v1 doctor checks matching and mismatched Hindsight worker identities")
print("PASS Hindsight stable worker identity runtime contract")
