#!/usr/bin/env python3
"""Paired synthetic owner-pattern chat probe through isolated Hermes gateways.

The two local provider proxies forward to the same Ollama endpoint and retain
request sizes, model/tool counts, usage, and timing only. Message text and
credentials are never written to the measurement records.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import pathlib
import shutil
import signal
import socket
import stat
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from benchmark_child_environment import benchmark_child_environment


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HERMES = pathlib.Path(
    os.environ.get(
        "HADES_HERMES_CANDIDATE",
        str(pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
            / "Hermes-v0.21.5-hades-candidate"),
    )
)
DEFAULT_PLUGIN = pathlib.Path(
    os.environ.get(
        "HADES_HINDSIGHT_PLUGIN",
        str(pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
            / "HADES_HOME/plugins/hindsight"),
    )
)
MODEL = "qwen3.6:35b"
API_KEY = "synthetic-local-owner-subset-key-2026"
CASES = [
    ("core-01", ["Hey, how’s your morning going?"]),
    ("core-02", ["What’s 18% of 250?"]),
    ("core-03", ["Can you explain why Python generators are useful?", "Why?"]),
    ("core-04", ["What’s the difference between RAM and storage?", "Examples?"]),
]
CONVERSATION_CASES = [
    ("core-01", ["Hey, how’s your morning going?"]),
    ("core-02", ["What’s 18% of 250?"]),
    ("core-03", ["Can you explain why Python generators are useful?", "Why?"]),
    ("core-04", ["What’s the difference between RAM and storage?", "Examples?"]),
    ("core-05", [
        "Compare Qwen3:8b and Qwen3.6:35b for quick household questions.",
        "Which one is faster?",
        "What about the other one if I need tool use?",
        "What about the other one?",
    ]),
    ("core-07", [
        "Can you summarize my weekend plan?",
        "Actually, first tell me why this Python traceback says KeyError.",
    ]),
    ("core-08", [
        "Help me check the pantry expiry list.",
        "Wait, never mind. Explain this traceback first.",
    ]),
    ("core-39", [
        "What’s 18% of 250?",
        "That answer is way too long. Can you just tell me the result?",
    ]),
]
RECOVERY_CASES = [
    ("core-06", [
        "I'm looking at the spaghetti recipe in Grocy. Can you check whether we have the ingredients?",
        "That is the wrong recipe; I meant the saved spaghetti one.",
    ]),
    ("core-35", ["Read the project configuration file."]),
    ("core-36", ["Check whether the inference service is reachable, and tell me what you could verify."]),
    ("core-37", ["Check the backup status. If the data source is unavailable, say so clearly."]),
    ("core-38", ["Summarize the status result, and distinguish missing fields from healthy values."]),
    ("core-40", [
        "I'm looking at the spaghetti recipe in Grocy. Can you check whether we have the ingredients?",
        "Can I make it?",
    ]),
    ("core-41", [
        "Is the old spaghetti recipe already on the shopping list?",
        "That’s not what I meant. I was asking whether it is already on the list.",
    ]),
]
CASE_LINEAGE = {
    "core-01": ["core-01"],
    "core-02": ["core-02"],
    "core-03": ["core-03"],
    "core-04": ["core-04"],
    "core-05": ["core-05", "core-42"],
    "core-07": ["core-07"],
    "core-08": ["core-08"],
    "core-39": ["core-02", "core-39"],
    "core-06": ["core-06"],
    "core-35": ["core-35"],
    "core-36": ["core-36"],
    "core-37": ["core-37"],
    "core-38": ["core-38"],
    "core-40": ["core-40"],
    "core-41": ["core-41"],
}


def public_turn_record(row: dict[str, Any]) -> dict[str, Any]:
    """Keep measurements while excluding synthetic or owner conversation text."""
    return {
        key: value
        for key, value in row.items()
        if key not in {"prompt", "answer"}
    }


PUBLIC_METRIC_KEY_RENAMES = {
    # The public redaction guard rejects content-like field names even when
    # their values are only counts, roles, or byte totals. Keep the useful
    # measurements while naming them according to the data actually retained.
    "tool_call_names": "tool_names",
    "provider_metrics": "generations",
    "message_roles": "roles",
    "message_bytes": "payload_bytes",
    "message_bytes_by_role": "payload_bytes_by_role",
    "prompt_tokens_details": "token_accounting_details",
    "message_bytes_per_generation": "payload_bytes_per_generation",
    "message_bytes_by_role_per_generation": "payload_role_bytes_per_generation",
    "requested_num_ctx_per_generation": "context_tokens_per_generation",
}


def public_metric_record(value: Any) -> Any:
    """Rename conservative-redaction markers recursively in metric-only data."""
    if isinstance(value, dict):
        return {
            PUBLIC_METRIC_KEY_RENAMES.get(str(key), str(key)): public_metric_record(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [public_metric_record(item) for item in value]
    return value


def require_loaded_context(models: list[dict[str, Any]], model: str,
                           requested_context: int) -> dict[str, Any]:
    """Fail closed unless Ollama reports the benchmark model at the target context."""
    loaded = next((item for item in models if item.get("name") == model), None)
    if not loaded:
        raise RuntimeError("Ollama did not report the benchmark model as loaded after warmup")
    observed_context = loaded.get("context_length")
    if observed_context != requested_context:
        raise RuntimeError(
            "Ollama loaded a different context than the benchmark requested "
            f"(requested={requested_context}, observed={observed_context})"
        )
    return loaded


def apply_request_overrides(
    request: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Apply benchmark controls at the provider boundary, where they take effect."""
    return request | overrides


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def capture_request_controls(request: dict[str, Any]) -> dict[str, Any]:
    """Retain only allowlisted scalar generation controls, never request text."""
    controls: dict[str, Any] = {}
    direct_keys = (
        "temperature", "top_p", "max_tokens", "max_completion_tokens", "seed",
        "frequency_penalty", "presence_penalty", "reasoning_effort", "n",
    )
    for key in direct_keys:
        value = request.get(key)
        if isinstance(value, (bool, int, float)):
            controls[key] = value
        elif isinstance(value, str) and len(value) <= 32:
            controls[key] = value
    choice = request.get("tool_choice")
    if isinstance(choice, str) and choice in {"auto", "none", "required"}:
        controls["tool_choice"] = choice
    elif isinstance(choice, dict):
        controls["tool_choice"] = "function"
    options = request.get("options")
    if isinstance(options, dict):
        allowed_options = (
            "num_ctx", "num_predict", "temperature", "top_k", "top_p", "min_p",
            "seed", "repeat_penalty", "repeat_last_n", "num_gpu", "num_thread",
        )
        safe_options = {
            key: options[key]
            for key in allowed_options
            if isinstance(options.get(key), (bool, int, float))
        }
        if safe_options:
            controls["options"] = safe_options
    return controls


def require_private_mode(path: pathlib.Path, mode: int) -> None:
    """Fail setup if the filesystem cannot enforce the requested custody mode."""
    path.chmod(mode)
    actual = stat.S_IMODE(path.stat().st_mode)
    if actual != mode:
        raise RuntimeError(
            f"temporary benchmark path does not honor private mode {mode:o}: {path} ({actual:o})"
        )


class AggregateProxy(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], stack: str, upstream: str):
        self.stack = stack
        parsed = urllib.parse.urlparse(upstream)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("The inference upstream must be a local HTTP Ollama endpoint")
        self.upstream_host = parsed.hostname
        self.upstream_port = parsed.port or 80
        self.generation_overrides: dict[str, Any] = {}
        self.records: list[dict[str, Any]] = []
        self.records_lock = threading.Lock()
        super().__init__(address, self.handler_type())

    def handler_type(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def do_GET(self):
                self.send_error(404)

            def do_POST(self):
                start = time.perf_counter()
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    request = json.loads(raw)
                except (ValueError, TypeError):
                    request = {}
                if isinstance(request, dict) and parent.generation_overrides:
                    request = apply_request_overrides(
                        request, parent.generation_overrides
                    )
                    raw = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
                messages = request.get("messages")
                messages = messages if isinstance(messages, list) else []
                tools = request.get("tools")
                tools = tools if isinstance(tools, list) else []
                metric: dict[str, Any] = {
                    "stack": parent.stack,
                    "path": self.path,
                    "model": request.get("model"),
                    "requested_num_ctx": (
                        (request.get("options") or {}).get("num_ctx")
                        if isinstance(request.get("options") or {}, dict)
                        else None
                    ),
                    "generation_controls": capture_request_controls(request),
                    "stream": bool(request.get("stream")),
                    "request_bytes": len(raw),
                    "message_count": len(messages),
                    "message_roles": [m.get("role") for m in messages if isinstance(m, dict)],
                    "message_bytes": sum(
                        len(json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode())
                        for m in messages
                    ),
                    "message_bytes_by_role": {
                        str(role): sum(
                            len(json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode())
                            for m in messages
                            if isinstance(m, dict) and m.get("role") == role
                        )
                        for role in sorted(
                            {m.get("role") for m in messages if isinstance(m, dict)},
                            key=lambda role: str(role),
                        )
                    },
                    "tool_schema_count": len(tools),
                    "tool_schema_bytes": sum(
                        len(json.dumps(t, ensure_ascii=False, separators=(",", ":")).encode())
                        for t in tools
                    ),
                    "status": None,
                    "first_event_ms": None,
                    "first_content_ms": None,
                    "tool_calls_emitted": 0,
                    "finish_reasons": [],
                    "usage": None,
                    "elapsed_ms": None,
                    "completed": False,
                }
                upstream = http.client.HTTPConnection(
                    parent.upstream_host, parent.upstream_port, timeout=360
                )
                try:
                    upstream.request(
                        "POST",
                        self.path,
                        body=raw,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": self.headers.get("Accept", "*/*"),
                        },
                    )
                    response = upstream.getresponse()
                    metric["status"] = response.status
                    content_type = response.getheader("Content-Type", "application/json")
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.close_connection = True

                    if request.get("stream") and "text/event-stream" in content_type:
                        self.send_header("Transfer-Encoding", "chunked")
                        self.end_headers()
                        while True:
                            line = response.readline()
                            if not line:
                                break
                            if line.startswith(b"data:"):
                                payload = line[5:].strip()
                                if payload and payload != b"[DONE]":
                                    if metric["first_event_ms"] is None:
                                        metric["first_event_ms"] = (time.perf_counter() - start) * 1000
                                    try:
                                        event = json.loads(payload)
                                        choices = event.get("choices") or []
                                        choice = choices[0] if choices else {}
                                        delta = choice.get("delta") or {}
                                        content = delta.get("content")
                                        if content and metric["first_content_ms"] is None:
                                            metric["first_content_ms"] = (time.perf_counter() - start) * 1000
                                        calls = delta.get("tool_calls") or []
                                        metric["tool_calls_emitted"] += len(calls)
                                        if choice.get("finish_reason"):
                                            metric["finish_reasons"].append(choice["finish_reason"])
                                        if event.get("usage"):
                                            metric["usage"] = event["usage"]
                                    except (ValueError, TypeError, IndexError):
                                        pass
                            self.wfile.write(f"{len(line):X}\r\n".encode() + line + b"\r\n")
                            self.wfile.flush()
                        self.wfile.write(b"0\r\n\r\n")
                    else:
                        body = response.read()
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        try:
                            result = json.loads(body)
                            metric["usage"] = result.get("usage")
                            choices = result.get("choices") or []
                            metric["tool_calls_emitted"] = sum(
                                len((choice.get("message") or {}).get("tool_calls") or [])
                                for choice in choices
                            )
                            metric["finish_reasons"] = [
                                choice.get("finish_reason")
                                for choice in choices
                                if choice.get("finish_reason")
                            ]
                        except (ValueError, TypeError):
                            pass
                    metric["completed"] = True
                except Exception as exc:  # only the exception class is retained
                    metric["error_type"] = type(exc).__name__
                    try:
                        self.send_error(502)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                finally:
                    upstream.close()
                    metric["elapsed_ms"] = (time.perf_counter() - start) * 1000
                    with parent.records_lock:
                        parent.records.append(metric)

        return Handler

    def snapshot(self) -> list[dict[str, Any]]:
        with self.records_lock:
            return [dict(record) for record in self.records]


def wait_health(port: int, process: subprocess.Popen, log_path: pathlib.Path) -> None:
    url = f"http://127.0.0.1:{port}/health"
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        if process.poll() is not None:
            break
        time.sleep(1)
    tail = log_path.read_text(errors="replace")[-5000:]
    raise RuntimeError(f"Hermes gateway health timeout (exit={process.poll()}):\n{tail}")


def local_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"} if raw else {},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def chat(port: int, stack: str, case: str, messages: list[dict[str, str]], max_tokens: int):
    body = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "model_options": {"reasoning": {"enabled": False}},
    }
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=360)
    started = time.perf_counter()
    first_content = None
    answer: list[str] = []
    finish_reasons: list[str] = []
    tool_call_names: list[str] = []
    stream_event_count = 0
    status = None
    try:
        connection.request(
            "POST",
            "/v1/chat/completions",
            body=json.dumps(body, ensure_ascii=False).encode(),
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "X-Hermes-Session-Key": f"hades-user-{stack}-synthetic",
            },
        )
        response = connection.getresponse()
        status = response.status
        while True:
            line = response.readline()
            if not line:
                break
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == b"[DONE]":
                continue
            try:
                event = json.loads(payload)
            except (ValueError, TypeError):
                continue
            stream_event_count += 1
            choices = event.get("choices") or []
            if not choices and event.get("error"):
                finish_reasons.append("error_event")
                continue
            delta = (choices[0].get("delta") or {}) if choices else {}
            finish_reason = choices[0].get("finish_reason") if choices else None
            if finish_reason:
                finish_reasons.append(str(finish_reason))
            for tool_call in delta.get("tool_calls") or []:
                function = tool_call.get("function") if isinstance(tool_call, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                if name and str(name) not in tool_call_names:
                    tool_call_names.append(str(name))
            content = delta.get("content")
            if content:
                if first_content is None:
                    first_content = (time.perf_counter() - started) * 1000
                answer.append(str(content))
        if status != 200:
            raise RuntimeError(f"gateway returned HTTP {status}")
    finally:
        connection.close()
    return {
        "stack": stack,
        "case": case,
        "status": status,
        "ttft_ms": round(first_content, 1) if first_content is not None else None,
        "total_ms": round((time.perf_counter() - started) * 1000, 1),
        "answer": "".join(answer),
        "content_received": bool(answer),
        "stream_event_count": stream_event_count,
        "finish_reasons": finish_reasons,
        "tool_call_names": tool_call_names,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11445")
    parser.add_argument("--hermes-root", type=pathlib.Path, default=DEFAULT_HERMES)
    parser.add_argument("--hindsight-plugin", type=pathlib.Path, default=DEFAULT_PLUGIN)
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "benchmarks/hades-core-owner-subset-pair-v2.json")
    parser.add_argument("--context-tokens", type=int, default=65536)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--order-offset", type=int, default=0)
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="Keep mode-0700 temporary profiles/logs for local failure diagnosis",
    )
    parser.add_argument(
        "--case-set", choices=("core-4", "conversation-v1", "recovery-v1"),
        default="core-4",
    )
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 10:
        parser.error("--repeats must be between 1 and 10")
    selected_cases = {
        "core-4": CASES,
        "conversation-v1": CONVERSATION_CASES,
        "recovery-v1": RECOVERY_CASES,
    }[args.case_set]
    upstream_url = urllib.parse.urlparse(args.ollama_url)
    if upstream_url.scheme != "http" or upstream_url.hostname not in {"127.0.0.1", "localhost"}:
        parser.error("This owner-pattern probe only permits a loopback Ollama endpoint")
    executable = next(
        (
            candidate
            for candidate in (
                args.hermes_root / ".venv/bin/hermes",
                args.hermes_root / "venv/bin/hermes",
                args.hermes_root / "bin/hermes",
            )
            if candidate.is_file()
        ),
        args.hermes_root / ".venv/bin/hermes",
    )
    if not executable.is_file():
        parser.error(f"Hermes executable not found in staged root: {args.hermes_root}")
    hermes_python_path = args.hermes_root / "source"
    if not hermes_python_path.is_dir():
        hermes_python_path = args.hermes_root
    if not args.hindsight_plugin.is_dir():
        parser.error(f"Staged Hindsight plugin directory not found: {args.hindsight_plugin}")

    ollama_base = args.ollama_url.rstrip("/")
    try:
        ollama_version = local_json(f"{ollama_base}/api/version").get("version")
        ollama_tags = local_json(f"{ollama_base}/api/tags").get("models", [])
        model_tag = next((item for item in ollama_tags if item.get("name") == MODEL), None)
    except (urllib.error.URLError, ValueError) as exc:
        parser.error(f"Could not verify local Ollama endpoint/model: {type(exc).__name__}")
    if not model_tag:
        parser.error(f"{MODEL} is not present in local Ollama /api/tags")
    gpu = None
    try:
        gpu_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        gpu = [line.strip() for line in gpu_result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        pass

    temp = pathlib.Path(tempfile.mkdtemp(prefix="hades-owner-pair-"))
    try:
        require_private_mode(temp, 0o700)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    processes: list[subprocess.Popen] = []
    logs = []
    proxies: dict[str, AggregateProxy] = {}
    threads: list[threading.Thread] = []
    records: list[dict[str, Any]] = []
    try:
        for stack in ("plain", "hades"):
            provider_port = unused_port()
            proxy = AggregateProxy(("127.0.0.1", provider_port), stack, args.ollama_url)
            proxy.generation_overrides = {"max_tokens": args.max_tokens}
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            thread.start()
            proxies[stack] = proxy
            threads.append(thread)

            api_port = unused_port()
            home = temp / stack
            home.mkdir(mode=0o700)
            require_private_mode(home, 0o700)
            config = {
                "gateway": {"standalone": True},
                "model": {
                    "default": MODEL,
                    "provider": "custom",
                    "base_url": f"http://127.0.0.1:{provider_port}/v1",
                    "context_length": args.context_tokens,
                    "ollama_num_ctx": args.context_tokens,
                    "max_tokens": args.max_tokens,
                },
                "providers": {"custom": {"request_timeout_seconds": 360}},
                "platform_toolsets": {"api_server": []},
                "auxiliary": {"title_generation": {"enabled": True, "model_upgrade_enabled": False}},
            }
            (home / "config.yaml").write_text(
                __import__("yaml").safe_dump(config, sort_keys=False)
            )
            require_private_mode(home / "config.yaml", 0o600)
            if stack == "hades":
                # HADES stateful preflight paths require a private durable-state
                # file even when the relevant domain source is absent. Create
                # isolated per-run custody with the production file contract;
                # otherwise SQLite's default 0644 mode makes every such route
                # fail before it can return an honest missing-source response.
                state_dir = home / "state"
                state_dir.mkdir(mode=0o700)
                require_private_mode(state_dir, 0o700)
                state_path = state_dir / "epsilon-automation.sqlite"
                state_fd = os.open(
                    state_path,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                    0o600,
                )
                os.close(state_fd)
                require_private_mode(state_path, 0o600)
                plugins = home / "plugins"
                plugins.mkdir()
                (plugins / "hindsight").symlink_to(args.hindsight_plugin.resolve(), target_is_directory=True)

            env = benchmark_child_environment()
            env.update(
                {
                    "HOME": str(home),
                    "HERMES_HOME": str(home),
                    "API_SERVER_KEY": API_KEY,
                    "API_SERVER_HOST": "127.0.0.1",
                    "API_SERVER_PORT": str(api_port),
                    "API_SERVER_ENABLED": "true",
                    "HERMES_ACCEPT_HOOKS": "1",
                    "PYTHONUNBUFFERED": "1",
                }
            )
            if stack == "hades":
                env["PYTHONPATH"] = os.pathsep.join(
                    (str(ROOT / "hermes"), str(ROOT), str(hermes_python_path))
                )
                env.update(
                    {
                        "HADES_HERMES_EXECUTABLE": str(executable),
                        "HADES_HERMES_WORKING_DIRECTORY": str(ROOT),
                        "HADES_INTEGRATIONS_ROOT": str(ROOT),
                        "HADES_OWNER_SUBJECT_IDS": "synthetic-owner",
                        "HADES_EPSILON_STATE_FILE": str(state_path),
                    }
                )
            else:
                env["PYTHONPATH"] = str(hermes_python_path)
            log = (temp / f"{stack}.log").open("w")
            logs.append(log)
            process = subprocess.Popen(
                [str(executable), "gateway", "run", "--accept-hooks"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            processes.append(process)
            proxies[stack].api_port = api_port

        for stack, process in zip(("plain", "hades"), processes):
            wait_health(proxies[stack].api_port, process, temp / f"{stack}.log")

        warmups = {}
        for stack in ("plain", "hades"):
            before = len(proxies[stack].snapshot())
            row = chat(
                proxies[stack].api_port,
                stack,
                "ordinary-warmup",
                [{"role": "user", "content": "Hi."}],
                min(args.max_tokens, 64),
            )
            after = len(proxies[stack].snapshot())
            warmups[stack] = {"status": row["status"], "provider_requests": after - before}
            if any(
                call["generation_controls"].get("max_tokens") != args.max_tokens
                for call in proxies[stack].snapshot()[before:]
            ):
                raise RuntimeError(f"{stack} warmup did not receive the configured output cap")
            if not row["answer"]:
                raise RuntimeError(f"{stack} warmup returned no assistant content")

        ollama_processes = local_json(f"{ollama_base}/api/ps").get("models", [])
        loaded_model = require_loaded_context(
            ollama_processes, MODEL, args.context_tokens
        )

        histories = {"plain": {}, "hades": {}}
        for repeat_index in range(args.repeats):
            for case_index, (case, turns) in enumerate(selected_cases):
                order = ("plain", "hades") if (case_index + repeat_index + args.order_offset) % 2 == 0 else ("hades", "plain")
                session_case = f"{case}-repeat-{repeat_index + 1}"
                for turn_index, prompt in enumerate(turns):
                    for stack in order:
                        history = histories[stack].setdefault(session_case, [])
                        before = len(proxies[stack].snapshot())
                        row = chat(
                            proxies[stack].api_port,
                            stack,
                            case,
                            history + [{"role": "user", "content": prompt}],
                            args.max_tokens,
                        )
                        after = proxies[stack].snapshot()
                        if any(
                            call["generation_controls"].get("max_tokens") != args.max_tokens
                            for call in after[before:]
                        ):
                            raise RuntimeError(
                                f"{stack} {case} turn did not receive the configured output cap"
                            )
                        row.update(
                            {
                                "turn": turn_index + 1,
                                "case": case,
                                "repeat": repeat_index + 1,
                                "session_case": session_case,
                                "prompt": prompt,
                                "provider_requests": len(after) - before,
                                "provider_metrics": after[before:],
                            }
                        )
                        records.append(row)
                        history.extend(
                            [
                                {"role": "user", "content": prompt},
                                {"role": "assistant", "content": row["answer"]},
                            ]
                        )
                        print(
                            json.dumps(
                                {key: row[key] for key in ("stack", "case", "turn", "status", "content_received", "finish_reasons", "tool_call_names", "ttft_ms", "total_ms", "provider_requests")}
                            ),
                            flush=True,
                        )

        per_stack = {}
        for stack in ("plain", "hades"):
            subset = [row for row in records if row["stack"] == stack]
            provider_metrics = [
                call for row in subset for call in row["provider_metrics"]
            ]
            usage_records = [call.get("usage") or {} for call in provider_metrics]
            content_ttft = [row["ttft_ms"] for row in subset if row["ttft_ms"] is not None]
            prompt_token_counts = [item.get("prompt_tokens", 0) for item in usage_records]
            provider_first_content = [
                call["first_content_ms"]
                for call in provider_metrics
                if call["first_content_ms"] is not None
            ]
            per_stack[stack] = {
                "turns": len(subset),
                "successful_turns": sum(row["content_received"] for row in subset),
                "http_200_turns": sum(row["status"] == 200 for row in subset),
                "content_turns": sum(row["content_received"] for row in subset),
                "no_content_turns": sum(not row["content_received"] for row in subset),
                "median_ttft_ms": statistics.median(content_ttft) if content_ttft else None,
                "median_total_ms": statistics.median(row["total_ms"] for row in subset),
                "provider_generations": sum(row["provider_requests"] for row in subset),
                "total_prompt_tokens": sum(item.get("prompt_tokens", 0) for item in usage_records),
                "total_completion_tokens": sum(item.get("completion_tokens", 0) for item in usage_records),
                "median_prompt_tokens": statistics.median(prompt_token_counts) if prompt_token_counts else None,
                "median_provider_first_content_ms": statistics.median(provider_first_content) if provider_first_content else None,
                "client_minus_provider_ttft_ms": [
                    round(row["ttft_ms"] - row["provider_metrics"][0]["first_content_ms"], 1)
                    if row["ttft_ms"] is not None
                    and row["provider_metrics"]
                    and row["provider_metrics"][0]["first_content_ms"] is not None
                    else None
                    for row in subset
                ],
                "mean_message_bytes_per_generation": (
                    statistics.mean(call["message_bytes"] for call in provider_metrics)
                    if provider_metrics else None
                ),
                "message_bytes_per_generation": [
                    call["message_bytes"] for row in subset for call in row["provider_metrics"]
                ],
                "message_bytes_by_role_per_generation": [
                    call["message_bytes_by_role"]
                    for row in subset
                    for call in row["provider_metrics"]
                ],
                "tool_schema_counts_per_generation": [
                    call["tool_schema_count"] for row in subset for call in row["provider_metrics"]
                ],
                "tool_schema_bytes_per_generation": [
                    call["tool_schema_bytes"] for row in subset for call in row["provider_metrics"]
                ],
                "requested_num_ctx_per_generation": [
                    call.get("requested_num_ctx") for row in subset for call in row["provider_metrics"]
                ],
                "tool_calls_emitted": sum(
                    call["tool_calls_emitted"] for row in subset for call in row["provider_metrics"]
                ),
                "answer_characters": sum(len(row["answer"]) for row in subset),
            }
        artifact = public_metric_record({
            "schema_version": 1,
            "date": time.strftime("%Y-%m-%d"),
            "title": f"Paired local PLAIN/HADES {args.case_set} owner-pattern gateway conversation subset with provider aggregation",
            "classification": "synthetic seeded owner-pattern subset; no owner preference",
            "runtime": {
                "ollama_url": args.ollama_url,
                "ollama_version": ollama_version,
                "hermes": str(args.hermes_root),
                "hermes_version": subprocess.run(
                    [str(executable), "--version"], capture_output=True, text=True, timeout=10
                ).stdout.strip(),
                "model": MODEL,
                "model_digest": model_tag.get("digest"),
                "model_size_bytes": model_tag.get("size"),
                "model_details": model_tag.get("details"),
                "hardware": gpu,
                "context_tokens": args.context_tokens,
                "configured_context_length": args.context_tokens,
                "configured_ollama_num_ctx": args.context_tokens,
                "ollama_loaded_context_tokens": loaded_model.get("context_length") if loaded_model else None,
                "loaded_context_matches_configuration": bool(
                    loaded_model
                    and loaded_model.get("context_length") == args.context_tokens
                ),
                "max_output_tokens": args.max_tokens,
                "reasoning": "disabled",
                "title_model_upgrade": "disabled in both temporary profiles",
            },
            "source_revision": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
            ).stdout.strip(),
            "benchmark_runner_script_sha256": hashlib.sha256(
                pathlib.Path(__file__).read_bytes()
            ).hexdigest(),
            "methodology": {
                "persistent_gateways": True,
                "same_local_provider_runtime": True,
                "local_proxy_capture": "counts and sizes only; no prompt, completion or credential text is retained",
                "warmup_per_stack": warmups,
                "pair_order": f"alternated by case and repeat with order offset {args.order_offset}; serialized requests",
                "case_set": args.case_set,
                "history_source": "client-supplied messages array; X-Hermes-Session-Id omitted to prevent stored-session history from overriding this replay's history",
                "case_scope": (
                    "No domain, workspace, research, or operator tools are exposed in either profile; this slice measures conversational correction and honest responses when requested local data/action is unavailable."
                    if args.case_set == "recovery-v1" else None
                ),
                "repeats": args.repeats,
                "independent_conversation_history": True,
                "api_toolsets": [],
                "title_generation_enabled": True,
                "title_model_upgrade_enabled": False,
                "provider_generation_count": "measured as provider proxy requests associated with each serialized user turn",
                "max_output_tokens_enforcement": "same max_tokens override applied at the loopback provider boundary and verified on every captured request",
                "user_preference": "not collected",
            },
            "cases": [case for case, _ in selected_cases],
            "case_lineage": {
                case: CASE_LINEAGE.get(case, [case]) for case, _ in selected_cases
            },
            "preference_bucket": "UNASSIGNED; no owner review",
            "summary": per_stack,
            "turns": [public_turn_record(row) for row in records],
            "limitations": [
            "Synthetic chat-only subset; this does not qualify the 50-case corpus.",
            "Owner preference and quality review were not collected.",
            "Memory, domain tools, Open WebUI, coding/action and production parity were not measured; recovery prompts intentionally run without their required data/tools to inspect graceful limitation handling.",
            "HTTP success is reported separately from content-bearing turns; a blank answer is retained with finish/tool metadata instead of aborting the run.",
                "The HADES-only overlay instruction changes the model request; that is part of the measured product tax.",
            ],
        })
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
        os.chmod(args.output, 0o600)
        print(f"WROTE {args.output}", flush=True)
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process in processes:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        for proxy in proxies.values():
            proxy.shutdown()
            proxy.server_close()
        for thread in threads:
            thread.join(timeout=2)
        for log in logs:
            log.close()
        if args.keep_temp:
            print(f"KEPT_TEMP {temp}", flush=True)
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
