#!/usr/bin/env python3
"""Exercise HADES automatic qualification through the real Hermes provider and disposable Hindsight."""
from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "synthetic-hindsight-auto-retain"
FACT = "The synthetic user prefers violet comet-42 markers."
FACT_RESPONSE = json.dumps({"facts": [{
    "what": FACT,
    "when": "N/A",
    "where": "N/A",
    "who": "user",
    "why": "Synthetic extraction fixture.",
    "fact_type": "world",
    "entities": ["user", "violet comet-42 markers"],
}]})
model_requests: list[dict[str, str]] = []


def synthetic_fact_for(text: str) -> str:
    lowered = text.casefold()
    if "main project" in lowered and "hades" in lowered:
        return "The synthetic user's main project is HADES."
    if "lyxa" in lowered:
        return "The synthetic user's cat is named Lyxa."
    if "neovim" in lowered:
        return "The synthetic user prefers Neovim for coding."
    if "vim" in lowered or "editor" in lowered:
        return "The synthetic user prefers Vim for coding."
    return FACT


def synthetic_fact_family(text: str) -> str:
    lowered = text.casefold()
    if "cat" in lowered and "lyxa" in lowered:
        return "relationship"
    if "main project" in lowered:
        return "project"
    if "editor" in lowered or "vim" in lowered or "neovim" in lowered:
        return "editor"
    return "other"


class Model(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        messages = [message for message in body.get("messages", []) if isinstance(message, dict)]
        message_text = "\n".join(
            str(message.get("content", ""))
            for message in messages
        )
        user_text = "\n".join(str(message.get("content", "")) for message in messages if message.get("role") == "user")
        model_requests.append({
            "path": self.path, "model": str(body.get("model", "")),
            "consolidation": "source_fact_ids" in message_text,
            "user_text": user_text[:240],
        })
        source_ids = re.findall(r"\[([0-9a-f]{8}-[0-9a-f-]{27,})\]", message_text, re.IGNORECASE)
        new_fact_text = user_text
        if "### New facts" in new_fact_text:
            new_fact_text = new_fact_text.split("### New facts", 1)[1].split("### Existing observations", 1)[0]
        if "source_fact_ids" in message_text and source_ids:
            fact_rows = re.findall(
                r"^\[([0-9a-f]{8}-[0-9a-f-]{27,})\]\s*(.+)$",
                new_fact_text, re.IGNORECASE | re.MULTILINE,
            )
            grouped: dict[str, tuple[str, str]] = {}
            for fact_id, fact_text in fact_rows:
                family = synthetic_fact_family(fact_text)
                selected_fact = synthetic_fact_for(fact_text)
                previous = grouped.get(family)
                # The correction fixture deliberately batches the earlier Vim
                # assertion after the Neovim correction. Keep the explicit
                # correction authoritative instead of relying on batch order.
                if previous is None or (
                    "neovim" in selected_fact.casefold()
                    and "neovim" not in previous[1].casefold()
                ):
                    grouped[family] = (fact_id, selected_fact)
            observation_text = user_text.split("### Existing observations", 1)[-1]
            observation_rows = re.findall(
                r'"id"\s*:\s*"([0-9a-f]{8}-[0-9a-f-]{27,})".*?"text"\s*:\s*"([^"]*)"',
                observation_text, re.IGNORECASE | re.DOTALL,
            )
            creates, updates = [], []
            for family, (fact_id, selected_fact) in grouped.items():
                same_facet = next((
                    (observation_id, text)
                    for observation_id, text in observation_rows
                    if synthetic_fact_family(text) == family
                ), None)
                if same_facet:
                    updates.append({
                        "text": selected_fact,
                        "observation_id": same_facet[0],
                        "source_fact_ids": [fact_id],
                        "reason": "Same synthetic fact facet; update its current value.",
                    })
                else:
                    creates.append({
                        "text": selected_fact,
                        "source_fact_ids": [fact_id],
                        "reason": "Synthetic durable fact for recall qualification.",
                    })
            action = {"creates": creates, "updates": updates, "deletes": []}
            response_text = json.dumps(action)
        else:
            extracted_fact = synthetic_fact_for(user_text or message_text)
            response_text = json.dumps({"facts": [{
                "what": extracted_fact,
                "when": "N/A", "where": "N/A", "who": "user",
                "why": "Synthetic extraction fixture.", "fact_type": "world",
                "entities": ["user", "editor preference"],
            }]})
        if self.path.endswith("/api/chat"):
            result = {"model": MODEL, "message": {"role": "assistant", "content": response_text}, "done": True}
        else:
            result = {
                "id": "synthetic-auto-retain", "object": "chat.completion", "created": 1,
                "model": MODEL, "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        payload = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        return


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                            stderr=subprocess.PIPE if capture else subprocess.DEVNULL)
    return result.stdout.strip() if capture else ""


def image_pin() -> str:
    for line in (ROOT / "config/versions.env").read_text().splitlines():
        if line.startswith("HADES_HINDSIGHT_IMAGE="):
            return line.partition("=")[2].strip().strip("\"'")
    raise RuntimeError("pinned Hindsight image is not configured")


def wait_healthy(url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("disposable Hindsight did not become healthy")


def request_json(url: str, *, data: dict | None = None, method: str = "GET") -> dict:
    request = urllib.request.Request(
        url,
        data=None if data is None else json.dumps(data).encode(),
        headers={} if data is None else {"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> None:
    hermes_python = Path(os.environ.get("HADES_HERMES_PYTHON", ""))
    if not hermes_python.is_file():
        raise RuntimeError("set HADES_HERMES_PYTHON to the installed Hermes 0.21.2 Python")
    image = image_pin()
    run("docker", "image", "inspect", image)
    suffix = uuid.uuid4().hex[:10]
    name, volume = f"hades-auto-retain-{suffix}", f"hades-auto-retain-data-{suffix}"
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 0), Model)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    run("docker", "volume", "create", volume)
    try:
        run("docker", "run", "-d", "--name", name,
            "--add-host=host.docker.internal:host-gateway", "-p", "127.0.0.1::8888",
            "-v", f"{volume}:/home/hindsight/.pg0",
            "-e", "HINDSIGHT_API_HOST=0.0.0.0", "-e", "HINDSIGHT_API_PORT=8888",
            "-e", "HINDSIGHT_API_ENABLE_OBSERVATIONS=true", "-e", f"HINDSIGHT_API_WORKER_ID={name}",
            "-e", "HINDSIGHT_API_LLM_PROVIDER=ollama", "-e", f"HINDSIGHT_API_LLM_MODEL={MODEL}",
            "-e", f"HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:{server.server_port}/v1",
            "-e", "HINDSIGHT_API_LLM_API_KEY=synthetic", image)
        inspect = json.loads(run("docker", "inspect", name, capture=True))[0]
        port = inspect["NetworkSettings"]["Ports"]["8888/tcp"][0]["HostPort"]
        api = f"http://127.0.0.1:{port}"
        wait_healthy(api + "/health")
        request_json(api + "/v1/default/banks/hades-user-synthetic-beta",
                     data={"name": "Synthetic isolated actor"}, method="PUT")

        with tempfile.TemporaryDirectory(prefix="hades-auto-retain-hermes-") as temp_home:
            config_dir = Path(temp_home) / "hindsight"
            config_dir.mkdir(mode=0o700)
            (config_dir / "config.json").write_text(json.dumps({
                "mode": "local_external", "api_url": api,
                "bank_id_template": "hades-user-{user}", "auto_retain": True,
                "retain_async": False, "retain_every_n_turns": 1,
                "auto_recall": True, "recall_sync": True,
                # Narrow retrieval should pass only the top matching fact;
                # production remains at its existing 400-token setting.
                "recall_types": ["observation"], "budget": "low", "recall_max_tokens": 16,
            }), encoding="utf-8")
            env = os.environ.copy()
            env.update({
                "HERMES_HOME": temp_home,
                "HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS": "synthetic-alpha,synthetic-beta,synthetic-correction,synthetic-recall",
                "HADES_HINDSIGHT_URL": api,
                "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "hermes"), str(ROOT), env.get("PYTHONPATH", "")])),
            })
            worker = r'''
import json, sys
import sitecustomize
from plugins.memory.hindsight import HindsightMemoryProvider
mode, subject, session = sys.argv[1:4]
p = HindsightMemoryProvider()
p.initialize(session, platform="openwebui", user_id=subject, chat_id=session)
retain_calls = []
original_retain_batch = p._retain_batch
def observed_retain_batch(*args, **kwargs):
    retain_calls.append(True)
    return original_retain_batch(*args, **kwargs)
p._retain_batch = observed_retain_batch
if mode == "retain":
    p.sync_turn("I prefer concise technical answers.", "Assistant guessed a private fact: synthetic-secret-991.", session_id=session)
    drained = p._wait_for_retains_drained(60)
    retained_payload = " ".join(p._session_turns)
    print(json.dumps({"mode": mode, "bank": p._bank_id, "subject": p._user_id,
                      "drained": drained, "retain_calls": len(retain_calls),
                      "assistant_payload_absent": "synthetic-secret-991" not in retained_payload}))
    p.shutdown()
elif mode == "reject":
    p.sync_turn("The current server is healthy.", "Tool output: current status is healthy.", session_id=session)
    print(json.dumps({"mode": mode, "bank": p._bank_id, "subject": p._user_id, "retain_calls": len(retain_calls), "turns": len(p._session_turns)}))
    p.shutdown()
elif mode == "journey":
    prompts = json.loads(sys.argv[4])
    drains = []
    for prompt in prompts:
        p.sync_turn(prompt, "", session_id=session)
        drains.append(p._wait_for_retains_drained(60))
    print(json.dumps({"mode": mode, "bank": p._bank_id, "subject": p._user_id,
                      "drains": drains, "retain_calls": len(retain_calls)}))
    p.shutdown()
elif mode == "recall_suite":
    prompts = json.loads(sys.argv[4])
    drains = []
    for prompt in prompts:
        p.sync_turn(prompt, "", session_id=session)
        drains.append(p._wait_for_retains_drained(60))
    print(json.dumps({"mode": mode, "bank": p._bank_id, "subject": p._user_id,
                      "drains": drains, "retain_calls": len(retain_calls)}))
    p.shutdown()
else:
    query = sys.argv[4] if len(sys.argv) > 4 else "What personal answer style does this user prefer? concise technical answers"
    raw = p._recall(query)
    answer = p._do_recall(query)
    print(json.dumps({"mode": mode, "bank": p._bank_id, "subject": p._user_id,
                      "answer": answer[0], "count": answer[1],
                      "results": [{"text": item.text, "scores": getattr(item, "scores", None)} for item in raw]}))
    p.shutdown()
'''
            def invoke(mode: str, subject: str, session: str, payload: str | None = None) -> dict:
                extra_args = json.dumps([
                    "My preferred editor is Vim.",
                    "Actually, I switched to Neovim.",
                    "Actually, I switched to Neovim.",
                ]) if mode == "journey" else json.dumps([
                    "My preferred editor is Neovim.",
                    "My cat's name is Lyxa.",
                    "My main project is HADES.",
                ]) if mode == "recall_suite" else None
                args = [str(hermes_python), "-c", worker, mode, subject, session]
                if extra_args is not None:
                    args.append(extra_args)
                elif payload is not None:
                    args.append(payload)
                completed = subprocess.run(args,
                    cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=90, check=True)
                return json.loads(completed.stdout.strip().splitlines()[-1])

            retained = invoke("retain", "synthetic-alpha", "chat-alpha-a")
            if (retained["bank"] != "hades-user-synthetic-alpha" or not retained["drained"]
                    or retained["retain_calls"] != 1 or not retained["assistant_payload_absent"]):
                raise RuntimeError(f"native HADES retain did not drain into actor bank: {retained}")
            if not model_requests or any(item["model"] != MODEL for item in model_requests):
                raise RuntimeError("qualified native retain did not use the configured synthetic extraction model")
            rejected = invoke("reject", "synthetic-alpha", "chat-alpha-a")
            if rejected["retain_calls"] != 0 or rejected["turns"] != 0:
                raise RuntimeError(f"canonical operational state reached Hindsight retain after rejection: {rejected}")

            alpha_rows = request_json(api + "/v1/default/banks/hades-user-synthetic-alpha/memories/list?state=valid&limit=100").get("items", [])
            if not any("violet comet-42" in str(row.get("text", "")).casefold() for row in alpha_rows if isinstance(row, dict)):
                raise RuntimeError("qualified user turn did not persist in the canonical Hindsight bank")
            if any("synthetic-secret-991" in json.dumps(row).casefold() for row in alpha_rows if isinstance(row, dict)):
                raise RuntimeError("assistant inference was incorrectly persisted as user-authored memory")

            alpha_recall = invoke("recall", "synthetic-alpha", "chat-alpha-b")
            beta_recall = invoke("recall", "synthetic-beta", "chat-beta-a")
            if "violet comet-42" not in alpha_recall["answer"].casefold():
                api_recall = request_json(api + "/v1/default/banks/hades-user-synthetic-alpha/memories/recall", data={
                    "query": "What marker style does synthetic-alpha prefer? violet comet-42",
                    "budget": "low", "max_tokens": 1200,
                }, method="POST")
                raise RuntimeError(
                    f"new conversation did not recall Alpha's qualified memory: {alpha_recall}; "
                    f"persisted_rows={alpha_rows!r}; api_recall={api_recall!r}"
                )
            if "violet comet-42" in beta_recall["answer"].casefold():
                raise RuntimeError("Beta's fresh conversation recalled Alpha's private memory")
            print("PASS qualified user-authored context persisted through the native Hermes Hindsight provider")
            print("PASS fresh conversation recalled the fact for the same actor")
            print("PASS separate synthetic actor could not recall it")
            print("PASS rejected canonical state caused no extraction request or memory write")
            print("PASS assistant-only inferred secret was absent from canonical memory")

            correction = invoke("journey", "synthetic-correction", "chat-correction")
            corrected_recall = invoke(
                "recall", "synthetic-correction", "chat-correction-new", "Which coding editor do I prefer?"
            )
            if (correction["retain_calls"] != 3 or correction["drains"] != [True, True, True]
                    or "neovim" not in corrected_recall["answer"].casefold()
                    or re.search(r"\bvim\b", corrected_recall["answer"].casefold())):
                raise RuntimeError(
                    "automatic correction/deduplication did not leave one current editor preference: "
                    f"journey={correction}; recall={corrected_recall}"
                )
            if corrected_recall["count"] != 1:
                raise RuntimeError(f"repeated preference created duplicate recalled observations: {corrected_recall}")
            print("PASS same-actor preference correction updated the current Hindsight observation")
            print("PASS repeated preference did not create duplicate recalled observations")

            recall_suite = invoke("recall_suite", "synthetic-recall", "chat-recall-suite")
            editor_recall = invoke("recall", "synthetic-recall", "chat-recall-editor", "Which coding editor do I prefer?")
            cat_recall = invoke("recall", "synthetic-recall", "chat-recall-cat", "What is my cat's name?")
            project_recall = invoke("recall", "synthetic-recall", "chat-recall-project", "What is my main project?")
            recall_rows = request_json(
                api + "/v1/default/banks/hades-user-synthetic-recall/memories/list?state=valid&limit=100"
            ).get("items", [])
            first_text = lambda result: str((result.get("results") or [{}])[0].get("text", "")).casefold()
            if "neovim" not in first_text(editor_recall):
                raise RuntimeError(f"editor query did not rank the matching preference first: {editor_recall}")
            if "lyxa" not in first_text(cat_recall):
                raise RuntimeError(f"relationship query did not rank the matching name first: {cat_recall}")
            if "hades" not in first_text(project_recall):
                raise RuntimeError(f"project query did not rank the matching fact first: {project_recall}")
            if any(result["count"] != 1 for result in (editor_recall, cat_recall, project_recall)):
                raise RuntimeError(
                    "narrow recall query returned irrelevant observations despite the bounded token budget: "
                    f"editor={editor_recall}; relationship={cat_recall}; project={project_recall}"
                )
            print("PASS editor, relationship, and project queries rank their matching durable fact first")
            print("PASS each narrow query excludes unrelated synthetic observations within the bounded token budget")
    finally:
        server.shutdown()
        server.server_close()
        run("docker", "rm", "-f", name) if subprocess.run(["docker", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 else None
        run("docker", "volume", "rm", volume)


if __name__ == "__main__":
    main()
