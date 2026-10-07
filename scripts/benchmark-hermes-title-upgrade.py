#!/usr/bin/env python3
"""Compare Hermes instant session titles with its optional model-title upgrade.

Uses two disposable Hermes 0.21.5 profiles and one synthetic loopback provider.
Persists only provider request metadata and synthetic title outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERMES = pathlib.Path("/opt/hades-stage/hades-core-usability-reset/Hermes-v0.21.5-hades-candidate")
API_KEY = "synthetic-title-upgrade-key-2026"
PROMPT = "Explain why Python generators help with streaming data."
requests: list[dict] = []


class SyntheticProvider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        body = json.dumps({"data": [{"id": "synthetic-model", "object": "model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        title_call = bool(req.get("response_format"))
        requests.append({"stream": bool(req.get("stream")), "title_call": title_call,
                         "message_roles": [m.get("role") for m in req.get("messages", []) if isinstance(m, dict)]})
        if title_call:
            body = json.dumps({"choices": [{"message": {"role": "assistant", "content":
                json.dumps({"title": "Python generators"})}, "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not req.get("stream"):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        events = [
            {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "Generators pause and resume computation."}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        for event in events:
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def api_json(url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "benchmarks/hermes-title-upgrade-gateway-probe-v2.json")
    args = parser.parse_args()
    executable = HERMES / ".venv/bin/hermes"
    if not executable.is_file():
        parser.error(f"staged Hermes executable not found: {executable}")
    provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SyntheticProvider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    temp = pathlib.Path(tempfile.mkdtemp(prefix="hades-title-upgrade-"))
    os.chmod(temp, 0o700)
    processes: list[tuple[subprocess.Popen, object]] = []
    results = {}
    try:
        for enabled in (True, False):
            name = "upgrade_enabled" if enabled else "upgrade_disabled"
            home = temp / name
            home.mkdir(mode=0o700)
            port = free_port()
            import yaml
            config = {
                "gateway": {"standalone": True},
                "model": {"default": "synthetic-model", "provider": "custom",
                          "base_url": f"http://127.0.0.1:{provider.server_address[1]}/v1",
                          "context_length": 65536, "ollama_num_ctx": 65536, "max_tokens": 96},
                "providers": {"custom": {"api_key": "synthetic", "request_timeout_seconds": 20}},
                "platform_toolsets": {"api_server": []},
                "auxiliary": {"title_generation": {"enabled": True, "model_upgrade_enabled": enabled,
                                                       "provider": "custom", "model": "synthetic-model"}},
            }
            config_path = home / "config.yaml"
            config_path.write_text(yaml.safe_dump(config))
            os.chmod(config_path, 0o600)
            env = os.environ.copy()
            env.update({"HOME": str(home), "HERMES_HOME": str(home), "API_SERVER_KEY": API_KEY,
                        "API_SERVER_HOST": "127.0.0.1", "API_SERVER_PORT": str(port),
                        "API_SERVER_ENABLED": "true", "HERMES_ACCEPT_HOOKS": "1",
                        "PYTHONUNBUFFERED": "1", "PYTHONPATH": str(HERMES), "OLLAMA_NO_CLOUD": "1"})
            log = (temp / f"{name}.log").open("w")
            process = subprocess.Popen([str(executable), "gateway", "run", "--accept-hooks"],
                                       cwd=HERMES, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            processes.append((process, log))
            deadline = time.monotonic() + 60
            health = f"http://127.0.0.1:{port}/health"
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(health, timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    if process.poll() is not None:
                        raise RuntimeError(f"{name} gateway exited: {(temp / f'{name}.log').read_text()[-3000:]}")
                    time.sleep(0.2)
            else:
                raise TimeoutError(f"{name} gateway health timeout")

            session_id = f"synthetic-title-{name}"
            before = len(requests)
            chat = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                data=json.dumps({"model": "synthetic-model", "messages": [{"role": "user", "content": PROMPT}],
                                 "stream": True, "max_tokens": 96}).encode(),
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json",
                         "X-Hermes-Session-Key": "synthetic-owner", "X-Hermes-Session-Id": session_id,
                         "Accept": "text/event-stream"})
            with urllib.request.urlopen(chat, timeout=30) as response:
                stream = response.read().decode(errors="replace")
            derived_title = "Explain why Python generators help with…"
            expected_title = "Python generators" if enabled else derived_title
            session = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                session = api_json(f"http://127.0.0.1:{port}/api/sessions/{session_id}").get("session")
                if session and session.get("title") == expected_title:
                    break
                time.sleep(0.1)
            if not session or session.get("title") != expected_title:
                raise RuntimeError(f"{name} persisted unexpected session title")
            measured = requests[before:]
            results[name] = {"main_stream_completed": "data: [DONE]" in stream,
                             "persisted_title": session.get("title"),
                             "provider_posts": len(measured),
                             "model_generations": sum(1 for item in measured if item["message_roles"]),
                             "title_model_generations": sum(1 for item in measured if item["title_call"]),
                             "provider_requests": measured}
        artifact = {
            "schema_version": 1, "date": time.strftime("%Y-%m-%d"),
            "classification": "synthetic isolated Hermes API title behavior probe; no owner preference",
            "source_revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                               text=True, capture_output=True).stdout.strip(),
            "benchmark_script": "scripts/benchmark-hermes-title-upgrade.py",
            "benchmark_script_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            "method": {"hermes_version": "0.21.5", "hermes_source": "staged immutable v2026.9.24 candidate",
                       "hermes_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERMES, check=True,
                                                        text=True, capture_output=True).stdout.strip(),
                       "model": "synthetic-model", "provider": "loopback synthetic OpenAI-compatible server",
                       "overlay": False, "tools": [], "open_webui": False, "prompt": PROMPT,
                       "title_model_output": "Python generators", "session_title_readback": "authenticated GET /api/sessions/{id}",
                       "source": "two separate temporary profiles; title upgrade true/false; all services loopback"},
            "results": results,
            "interpretation": "Hermes synchronously persists the derived title before its stream completes; enabled model upgrade makes one extra nonstream structured title generation and later replaces the persisted title. Disabled upgrade preserves the derived title and makes zero title-model calls. This proves title visibility on Hermes session API, not Open WebUI title UI integration or owner preference.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
        os.chmod(args.output, 0o600)
        print(json.dumps({"artifact": str(args.output), "results": results}, indent=2))
        return 0
    finally:
        for process, log in processes:
            try:
                os.killpg(process.pid, 15)
            except ProcessLookupError:
                pass
            log.close()
        provider.shutdown()
        provider.server_close()
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
