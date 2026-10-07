#!/usr/bin/env python3
"""Exercise an authenticated Open WebUI chat through staged Hermes and Ollama.

Ollama must already be running on loopback with the pinned local Qwen model.
The disposable Open WebUI container is attached to an internal Docker network;
the host browser reaches its bridge IP and Hermes binds only to that bridge.
"""

from __future__ import annotations

import argparse
import http.client
import http.server
import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HERMES = pathlib.Path(
    "/opt/hades-stage/hades-core-usability-reset/Hermes-v0.21.5-hades-candidate"
)
DEFAULT_IMAGE = (
    "sha256:5135da5a53c99cbfd25e1d6f94ddad3da50b1f00f7527c251b35baa514ec81b3"
)
MODEL = "qwen3.6:35b"
EXPECTED_MODEL_DIGEST = (
    "a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c"
)
API_KEY = "synthetic-local-browser-key-2026"


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalModelProxy(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], ollama_port: int):
        super().__init__(address, self.Handler)
        self.ollama_port = ollama_port
        self.events: list[dict[str, object]] = []
        self.events_lock = threading.Lock()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            body = json.dumps(
                {"data": [{"id": MODEL, "object": "model", "owned_by": "local"}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            parent: LocalModelProxy = self.server  # type: ignore[assignment]
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            request = json.loads(raw)
            messages = request.get("messages") or []
            user_text = " ".join(
                str(message.get("content", ""))
                for message in messages
                if isinstance(message, dict) and message.get("role") == "user"
            )
            normalized = user_text.lower()
            if not user_text:
                kind = "setup"
            elif "concise title" in normalized or "generate a title" in normalized:
                kind = "title"
            elif "follow-up questions" in normalized:
                kind = "follow_up"
            elif "broad tags" in normalized:
                kind = "tags"
            else:
                kind = "chat"
            event: dict[str, object] = {
                "kind": kind,
                "stream": bool(request.get("stream")),
                "schema": bool(request.get("response_format")),
                "prompt_bytes": len(raw),
                "tool_schemas": len(request.get("tools") or []),
            }

            request["model"] = MODEL
            connection = http.client.HTTPConnection(
                "127.0.0.1", parent.ollama_port, timeout=300
            )
            started = time.monotonic()
            event["ollama_request_started_at_epoch_ms"] = time.time_ns() // 1_000_000
            try:
                connection.request(
                    "POST",
                    "/v1/chat/completions",
                    body=json.dumps(request).encode(),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                event["status"] = response.status
                self.send_response(response.status)
                self.send_header(
                    "Content-Type", response.getheader("Content-Type", "application/json")
                )
                self.send_header("Connection", "close")
                if request.get("stream"):
                    # Forward SSE lines as they arrive so this proxy preserves TTFT.
                    self.end_headers()
                    data_frames = 0
                    final_marker = False
                    while line := response.readline():
                        if line.startswith(b"data:"):
                            data_frames += 1
                            final_marker = final_marker or line.strip() == b"data: [DONE]"
                        self.wfile.write(line)
                        self.wfile.flush()
                    event["sse_data_frames"] = data_frames
                    event["sse_done_marker"] = final_marker
                else:
                    body = response.read()
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as exc:  # retain the failure type, never request text
                event["status"] = "error"
                event["error_type"] = type(exc).__name__
                try:
                    self.send_error(502)
                except OSError:
                    pass
            finally:
                event["ollama_response_finished_at_epoch_ms"] = time.time_ns() // 1_000_000
                event["duration_ms"] = round((time.monotonic() - started) * 1000)
                with parent.events_lock:
                    parent.events.append(event)
                connection.close()


def request_json(url: str, *, token: str | None = None) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-tasks", choices=("on", "off"), required=True)
    parser.add_argument(
        "--send-followup",
        action="store_true",
        help="send a natural 'Why?' immediately after the first answer appears",
    )
    parser.add_argument(
        "--hermes-source",
        type=pathlib.Path,
        default=pathlib.Path(os.environ.get("HADES_HERMES_CANDIDATE", DEFAULT_HERMES)),
    )
    parser.add_argument("--open-webui-image", default=DEFAULT_IMAGE)
    parser.add_argument("--ollama-port", type=int, default=11445)
    parser.add_argument(
        "--playwright-module",
        default=os.environ.get(
            "HADES_PLAYWRIGHT_MODULE",
            str(Path.home() / ".local/share/hades-playwright/node_modules/playwright"),
        ),
    )
    args = parser.parse_args()

    if not args.hermes_source.is_dir():
        parser.error(f"Hermes source directory not found: {args.hermes_source}")
    subprocess.run(["docker", "image", "inspect", args.open_webui_image], check=True,
                   stdout=subprocess.DEVNULL)
    model_rows = request_json(f"http://127.0.0.1:{args.ollama_port}/api/tags").get("models", [])
    model = next((row for row in model_rows if row.get("name") == MODEL), None)
    if not model or model.get("digest") != EXPECTED_MODEL_DIGEST:
        parser.error("staged Ollama model is missing or has an unexpected immutable digest")

    temporary = pathlib.Path(tempfile.mkdtemp(prefix="hades-local-browser-")).resolve()
    os.chmod(temporary, 0o700)
    proxy = LocalModelProxy(("127.0.0.1", 0), args.ollama_port)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    proxy_port = proxy.server_address[1]
    network = f"hades-browser-{os.getpid()}"
    container = network
    hermes_process: subprocess.Popen[bytes] | None = None
    hermes_log = None
    network_created = False
    container_started = False
    try:
        subprocess.run(["docker", "network", "create", "--internal", network],
                       check=True, stdout=subprocess.DEVNULL)
        network_created = True
        network_data = json.loads(
            subprocess.check_output(["docker", "network", "inspect", network], text=True)
        )[0]
        gateway = network_data["IPAM"]["Config"][0]["Gateway"]
        hermes_port = unused_port()

        import yaml

        hermes_home = temporary / "hermes"
        hermes_home.mkdir(mode=0o700)
        config = {
            "gateway": {"standalone": True},
            "model": {
                "default": MODEL,
                "provider": "custom",
                "base_url": f"http://127.0.0.1:{proxy_port}/v1",
                "context_length": 65536,
                "ollama_num_ctx": 65536,
                "max_tokens": 128,
            },
            "providers": {
                "custom": {"api_key": "local-only", "request_timeout_seconds": 60}
            },
            "platform_toolsets": {"api_server": []},
            "auxiliary": {
                "title_generation": {
                    "enabled": True,
                    "model_upgrade_enabled": False,
                    "provider": "custom",
                    "model": MODEL,
                }
            },
        }
        config_path = hermes_home / "config.yaml"
        config_path.write_text(yaml.safe_dump(config))
        os.chmod(config_path, 0o600)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(hermes_home),
                "HERMES_HOME": str(hermes_home),
                "API_SERVER_KEY": API_KEY,
                "API_SERVER_HOST": gateway,
                "API_SERVER_PORT": str(hermes_port),
                "API_SERVER_ENABLED": "true",
                "HERMES_ACCEPT_HOOKS": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTHONPATH": str(args.hermes_source),
                "OLLAMA_NO_CLOUD": "1",
            }
        )
        hermes_log = (temporary / "hermes.log").open("wb")
        hermes_process = subprocess.Popen(
            [str(args.hermes_source / ".venv/bin/hermes"), "gateway", "run", "--accept-hooks"],
            cwd=args.hermes_source,
            env=env,
            stdout=hermes_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        api_base = f"http://{gateway}:{hermes_port}"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"{api_base}/health", timeout=1).close()
                break
            except Exception:
                if hermes_process.poll() is not None:
                    hermes_log.flush()
                    raise RuntimeError((temporary / "hermes.log").read_text()[-3000:])
                time.sleep(0.2)
        else:
            raise TimeoutError("Hermes API gateway did not become healthy")

        subprocess.run(
            [
                "docker", "run", "-d", "--name", container, "--network", network,
                "--network-alias", "title-ui", "--add-host", f"host.docker.internal:{gateway}",
                "-e", "ENABLE_SIGNUP=true", "-e", "ENABLE_LOGIN_FORM=true",
                "-e", "ENABLE_OLLAMA_API=false", "-e", "WEBUI_SECRET_KEY=synthetic-ui-key",
                args.open_webui_image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        container_started = True
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            health = subprocess.run(
                ["docker", "inspect", container, "--format", "{{.State.Health.Status}}"],
                capture_output=True, text=True,
            )
            if health.returncode == 0 and health.stdout.strip() == "healthy":
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("Open WebUI did not become healthy")

        inspect = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]
        ui_ip = inspect["NetworkSettings"]["Networks"][network]["IPAddress"]
        browser_env = os.environ.copy()
        browser_env.update(
            {
                "WEBUI_URL": f"http://{ui_ip}:8080",
                "HERMES_URL": api_base,
                "HADES_PLAYWRIGHT_MODULE": args.playwright_module,
                "METADATA_TASKS": args.metadata_tasks,
                "SEND_FOLLOWUP": "on" if args.send_followup else "off",
            }
        )
        browser = subprocess.run(
            ["node", str(ROOT / "scripts" / "benchmark-openwebui-hermes-local-browser.js")],
            capture_output=True,
            text=True,
            env=browser_env,
            timeout=300,
        )
        if browser.stdout.strip():
            print("BROWSER", browser.stdout.strip())
        if browser.stderr.strip():
            print("BROWSER_ERROR", browser.stderr.strip()[-2500:])
        if browser.returncode:
            raise RuntimeError("authenticated browser flow failed")

        time.sleep(3)
        sessions = request_json(f"{api_base}/api/sessions", token=API_KEY).get("data", [])
        ollama_processes = request_json(
            f"http://127.0.0.1:{args.ollama_port}/api/ps"
        ).get("models", [])
        effective_context = next(
            (row.get("context_length") for row in ollama_processes if row.get("name") == MODEL),
            None,
        )
        with proxy.events_lock:
            events = list(proxy.events)
        generations = [event for event in events if event["kind"] != "setup"]
        print(
            json.dumps(
                {
                    "metadata_tasks": args.metadata_tasks,
                    "model": MODEL,
                    "model_digest": model["digest"],
                    "effective_context": effective_context,
                    "provider_posts": len(events),
                    "model_generations": len(generations),
                    "provider_events": events,
                    "hermes_session_titles": [row.get("title") for row in sessions[:8]],
                },
                indent=2,
            )
        )
        return 0
    finally:
        if container_started:
            subprocess.run(["docker", "rm", "-fv", container],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if network_created:
            subprocess.run(["docker", "network", "rm", network],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if hermes_process:
            try:
                os.killpg(hermes_process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                hermes_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(hermes_process.pid, signal.SIGKILL)
        if hermes_log:
            hermes_log.close()
        proxy.shutdown()
        proxy.server_close()
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
