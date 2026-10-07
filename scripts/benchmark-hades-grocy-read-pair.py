#!/usr/bin/env python3
"""Compare HADES direct expiry reads with Hermes native MCP on synthetic Grocy."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import signal
import shutil
import socket
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
HERMES = SHARED / "Hermes-v0.21.5-hades-candidate"
MODEL = "qwen3.6:35b"
KEY = "synthetic-grocy-ui-key"
MCP_SOURCE = '''from __future__ import annotations
import json, os, urllib.request
from pathlib import Path
from mcp.server import MCPServer
server = MCPServer("synthetic-grocy")
@server.tool()
def get_expiry_report(include_recipes: bool = False, recipe_name: str = "") -> str:
    """Read synthetic canonical Grocy data. Supply recipe_name for saved-recipe feasibility, or set include_recipes true only when the user asks what recipe uses expiring food. This tool never changes stock."""
    trace = {"tool": "get_expiry_report", "include_recipes": include_recipes, "recipe_name": recipe_name}
    with Path(os.environ["GROCY_TRACE_FILE"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(trace, sort_keys=True) + "\\n")
    request = urllib.request.Request(os.environ["GROCY_URL"].rstrip("/") + "/api/stock", headers={"GROCY-API-KEY": os.environ["GROCY_KEY"], "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        rows = json.load(response)
    from datetime import date, timedelta
    today, cutoff = date.today(), date.today() + timedelta(days=7)
    expired, expiring, missing = [], [], []
    for row in rows:
        name = str((row.get("product") or {}).get("name") or row.get("product_id") or "").strip()
        raw = str(row.get("best_before_date") or "")
        if not raw:
            if name: missing.append(name)
            continue
        try: due = date.fromisoformat(raw[:10])
        except ValueError:
            missing.append(name); continue
        item = f"{name} ({row.get('amount_aggregated', row.get('amount'))} units, {raw})"
        if due < today: expired.append(item)
        elif due <= cutoff: expiring.append(item)
    report = "Known expired: " + (", ".join(expired) or "none") + ". Known to expire within 7 days: " + (", ".join(expiring) or "none") + ". Expiry metadata is missing for: " + (", ".join(missing) or "none") + "."
    if include_recipes:
        def get(path):
            request = urllib.request.Request(os.environ["GROCY_URL"].rstrip("/") + path, headers={"GROCY-API-KEY": os.environ["GROCY_KEY"], "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response: return json.load(response)
        ids = {str(row.get("product_id")) for row in rows if str(row.get("best_before_date", ""))[:10] and today <= date.fromisoformat(str(row["best_before_date"])[:10]) <= cutoff}
        positions, recipes = get("/api/objects/recipes_pos"), get("/api/objects/recipes")
        recipe_ids = {str(row.get("recipe_id")) for row in positions if str(row.get("product_id")) in ids}
        names = [str(row.get("name")) for row in recipes if str(row.get("id")) in recipe_ids]
        report += " Saved recipes using food that expires within 7 days: " + (", ".join(names[:3]) or "none found") + "."
    if recipe_name.strip():
        def get(path):
            request = urllib.request.Request(os.environ["GROCY_URL"].rstrip("/") + path, headers={"GROCY-API-KEY": os.environ["GROCY_KEY"], "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response: return json.load(response)
        recipes, positions, products = get("/api/objects/recipes"), get("/api/objects/recipes_pos"), get("/api/objects/products")
        selected = next((row for row in recipes if recipe_name.casefold() in str(row.get("name", "")).casefold()), None)
        if selected is None:
            report += " No saved recipe matched the requested name " + recipe_name + "."
        else:
            product_by_id = {str(row.get("id")): row for row in products}
            required = {}
            for row in positions:
                if row.get("recipe_id") == selected.get("id"):
                    pid = str(row.get("product_id"))
                    required[pid] = required.get(pid, 0) + float(row.get("amount", 0))
            missing = []
            for pid, amount in required.items():
                have = next((float(row.get("amount_aggregated", row.get("amount", 0)) or 0) for row in rows if str(row.get("product_id")) == pid), 0)
                if have < amount:
                    name = str(product_by_id.get(pid, {}).get("name") or pid)
                    missing.append(f"{name} ({amount-have:g} more)")
            if missing:
                report += f" Saved recipe {selected.get('name')} still needs " + ", ".join(missing) + "."
            else:
                report += f" Grocy shows enough listed stock for saved recipe {selected.get('name')}."
    return report
server.run(transport="stdio")
'''


def load_helpers():
    path = ROOT / "scripts/benchmark-hades-owner-subset.py"
    spec = importlib.util.spec_from_file_location("owner_bench", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def wait_for(url: str, proc: subprocess.Popen | None = None, timeout: int = 30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc and proc.poll() is not None:
            raise RuntimeError(f"process exited early: {proc.args}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(.2)
    raise TimeoutError(f"service did not start: {url}")


def request_rows(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def start_gateway(stack, helpers, base: pathlib.Path, grocy_url: str, key_file: pathlib.Path):
    import yaml

    port = helpers.unused_port()
    proxy = helpers.AggregateProxy(("127.0.0.1", port), stack, "http://127.0.0.1:11445")
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    api_port = helpers.unused_port()
    home = base / stack
    home.mkdir(mode=0o700)
    config = {
        "gateway": {"standalone": True},
        "model": {"default": MODEL, "provider": "custom", "base_url": f"http://127.0.0.1:{port}/v1", "ollama_num_ctx": 65536, "max_tokens": 256},
        "providers": {"custom": {"request_timeout_seconds": 240}},
        "platform_toolsets": {"api_server": []},
        "auxiliary": {"title_generation": {"enabled": False}},
    }
    if stack == "plain":
        config["mcp_servers"] = {"grocy": {
            "command": str(HERMES / ".venv/bin/python"),
            "args": [str(base / "synthetic_grocy_mcp.py")],
            "env": {"GROCY_URL": grocy_url, "GROCY_KEY": KEY, "GROCY_TRACE_FILE": str(base / "plain_mcp_calls.jsonl")},
            "enabled": True,
            "timeout": 15,
            "tools": {"include": ["get_expiry_report"]},
        }}
    else:
        (home / "plugins").mkdir()
        (home / "plugins/hindsight").symlink_to((SHARED / "HADES_HOME/plugins/hindsight").resolve(), target_is_directory=True)
    config_path = home / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    os.chmod(config_path, 0o600)
    env = os.environ.copy()
    env.update({
        "HOME": str(home), "HERMES_HOME": str(home),
        "API_SERVER_KEY": helpers.API_KEY, "API_SERVER_HOST": "127.0.0.1",
        "API_SERVER_PORT": str(api_port), "API_SERVER_ENABLED": "true",
        "HERMES_ACCEPT_HOOKS": "1", "PYTHONUNBUFFERED": "1",
        "OLLAMA_NO_CLOUD": "1", "HADES_OWNER_SUBJECT_IDS": "synthetic-owner",
        "HADES_GROCY_URL": grocy_url, "HADES_GROCY_API_KEY_FILE": str(key_file),
        "PYTHONPATH": str(HERMES) if stack == "plain" else os.pathsep.join((str(ROOT / "hermes"), str(ROOT), str(HERMES))),
    })
    if stack == "hades":
        env.update({"HADES_HERMES_EXECUTABLE": str(HERMES / ".venv/bin/hermes"), "HADES_HERMES_WORKING_DIRECTORY": str(ROOT), "HADES_INTEGRATIONS_ROOT": str(ROOT)})
    log = (base / f"{stack}.log").open("w")
    process = subprocess.Popen([str(HERMES / ".venv/bin/hermes"), "gateway", "run", "--accept-hooks"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    wait_for(f"http://127.0.0.1:{api_port}/health", process, 90)
    return {"stack": stack, "api_port": api_port, "proxy": proxy, "thread": thread, "process": process, "log": log}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "benchmarks/hades-core-grocy-read-pair-v6.json")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11445")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 2 or args.repeats > 10:
        parser.error("--repeats must be between 2 and 10 for counterbalanced paired samples")
    if args.ollama_url != "http://127.0.0.1:11445":
        parser.error("Use only the staged loopback Ollama endpoint at 11445")
    helpers = load_helpers()
    runtime_info = helpers.local_json(f"{args.ollama_url}/api/version")
    model_tags = helpers.local_json(f"{args.ollama_url}/api/tags").get("models", [])
    model_tag = next((row for row in model_tags if row.get("name") == MODEL), None)
    if not model_tag or model_tag.get("digest") != "a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c":
        raise RuntimeError("staged Ollama model tag/digest does not match the recorded Qwen3.6:35b control")
    temp = pathlib.Path(tempfile.mkdtemp(prefix="hades-grocy-pair-"))
    os.chmod(temp, 0o700)
    key_file = temp / "grocy-key"
    key_file.write_text(KEY)
    os.chmod(key_file, 0o600)
    mcp_script = temp / "synthetic_grocy_mcp.py"
    mcp_script.write_text(MCP_SOURCE)
    os.chmod(mcp_script, 0o600)
    port_file, request_log, fail_file = temp / "port", temp / "requests.jsonl", temp / "fail"
    fixture_env = os.environ.copy()
    fixture_env["HADES_SYNTHETIC_GROCY_FAILURE_FILE"] = str(fail_file)
    fixture = subprocess.Popen([str(HERMES / ".venv/bin/python"), str(ROOT / "scripts/synthetic-grocy-api.py"), "127.0.0.1", str(port_file), str(request_log)], env=fixture_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    gateways = {}
    try:
        wait_for_file = time.monotonic() + 10
        while not port_file.exists() and time.monotonic() < wait_for_file:
            if fixture.poll() is not None:
                raise RuntimeError("synthetic Grocy fixture exited before publishing its port")
            time.sleep(.1)
        port = int(port_file.read_text())
        grocy_url = f"http://127.0.0.1:{port}"
        for stack in ("plain", "hades"):
            gateways[stack] = start_gateway(stack, helpers, temp, grocy_url, key_file)
        # The sequence is counterbalanced across source health states.
        turns = []
        turn_specs = (
            ("available", "expiry", "What food is expiring soon?", ("plain", "hades")),
            ("available", "expiry_and_use", "What food is expiring soon, and what could we use it for?", ("hades", "plain")),
            ("available", "recipe_feasibility", "Can I make Synthetic Pancakes with what we have?", ("plain", "hades")),
            ("unavailable", "expiry", "What food is expiring soon?", ("plain", "hades")),
            ("unavailable", "expiry_and_use", "What food is expiring soon, and what could we use it for?", ("hades", "plain")),
            ("unavailable", "recipe_feasibility", "Can I make Synthetic Pancakes with what we have?", ("plain", "hades")),
        )
        for state in ("available", "unavailable"):
            if state == "available":
                fail_file.unlink(missing_ok=True)
            else:
                fail_file.touch(exist_ok=True)
            for repeat in range(1, args.repeats + 1):
                for spec_state, scenario, prompt, base_order in turn_specs:
                    if spec_state != state:
                        continue
                    order = tuple(reversed(base_order)) if repeat % 2 == 0 else base_order
                    for stack in order:
                        before = len(gateways[stack]["proxy"].snapshot())
                        fixture_before = request_rows(request_log)
                        mcp_before = request_rows(temp / "plain_mcp_calls.jsonl") if stack == "plain" else []
                        started = time.perf_counter()
                        try:
                            result = helpers.chat(gateways[stack]["api_port"], stack, f"grocy-r{repeat}-{state}-{scenario}-{stack}", [{"role": "user", "content": prompt}], 256)
                            error = None
                        except Exception as exc:
                            result = {"status": None, "answer": "", "ttft_ms": None, "total_ms": None}
                            error = type(exc).__name__
                        calls = gateways[stack]["proxy"].snapshot()[before:]
                        fixture_after = request_rows(request_log)
                        mcp_after = request_rows(temp / "plain_mcp_calls.jsonl") if stack == "plain" else []
                        turns.append({"repeat": repeat, "state": state, "scenario": scenario, "prompt": prompt, "stack": stack, "status": result["status"], "ttft_ms": result["ttft_ms"], "total_ms": result["total_ms"], "elapsed_ms": round((time.perf_counter()-started)*1000, 1), "answer": result["answer"], "provider_generations": len(calls), "tool_schema_count": sum(c.get("tool_schema_count", 0) for c in calls), "tool_calls_emitted": sum(c.get("tool_calls_emitted", 0) for c in calls), "fixture_requests": fixture_after[len(fixture_before):], "mcp_tool_calls": mcp_after[len(mcp_before):], "error_type": error})
                        print(json.dumps({"repeat": repeat, "state": state, "scenario": scenario, "stack": stack, "elapsed_ms": turns[-1]["elapsed_ms"], "generations": turns[-1]["provider_generations"], "answer": turns[-1]["answer"][:120]}), flush=True)
        requests = request_rows(request_log)
        mcp_calls = request_rows(temp / "plain_mcp_calls.jsonl")
        loaded_models = helpers.local_json(f"{args.ollama_url}/api/ps").get("models", [])
        loaded_model = next((row for row in loaded_models if row.get("name") == MODEL), None)
        loaded_context = loaded_model.get("context_length") if loaded_model else None
        if loaded_context != 65536:
            raise RuntimeError(
                f"Ollama effective context mismatch: expected 65536, got {loaded_context}"
            )
        artifact = {
            "schema_version": 1, "date": time.strftime("%Y-%m-%d"),
            "title": "Synthetic canonical Grocy expiry, recipe-use, and feasibility reads: HADES direct route vs Hermes MCP",
            "classification": "synthetic local tool-path probe; no owner preference or release qualification",
            "source_revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip(),
            "benchmark_script": "scripts/benchmark-hades-grocy-read-pair.py",
            "benchmark_script_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            "method": {"model": MODEL, "model_digest": model_tag["digest"], "quantization": "Q4_K_M", "runtime": f"Ollama {runtime_info.get('version')}", "effective_context_tokens": loaded_context, "reasoning": "disabled by benchmark request", "hermes": "0.21.5 staged candidate", "fixture": "authenticated loopback synthetic Grocy, same source and generated key", "plain_path": "one allowlisted native Hermes MCP read tool with expiry, saved-recipe-use, or recipe-name feasibility parameters", "hades_path": "direct canonical Grocy reads", "prompts": ["What food is expiring soon?", "What food is expiring soon, and what could we use it for?", "Can I make Synthetic Pancakes with what we have?"], "repeats": args.repeats, "order": "All available-source repeats run before a separate repeated 503 block; PLAIN/HADES order alternates per pair; v5 records post-outage recovery behavior", "writes": "fixture requests audited; expected GET only"},
            "turns": turns,
            "fixture_requests": {"count": len(requests), "methods": sorted({row["method"] for row in requests}), "all_authenticated": all(row.get("keyValid") for row in requests), "rows": requests},
            "mcp_tool_calls": mcp_calls,
            "summary": {
                f"{state}.{scenario}": {
                    stack: {
                        "samples": len(rows := [row for row in turns if row["state"] == state and row["scenario"] == scenario and row["stack"] == stack]),
                        "median_elapsed_ms": round(statistics.median(row["elapsed_ms"] for row in rows), 1),
                        "median_ttft_ms": round(statistics.median(row["ttft_ms"] for row in rows if row["ttft_ms"] is not None), 1),
                        "provider_generations": [row["provider_generations"] for row in rows],
                        "tool_calls_emitted": [row["tool_calls_emitted"] for row in rows],
                    }
                    for stack in ("plain", "hades")
                }
                for state, scenario, _prompt, _order in turn_specs
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
        os.chmod(args.output, 0o600)
        if not requests or any(row["method"] != "GET" for row in requests) or not all(row.get("keyValid") for row in requests):
            raise RuntimeError("fixture request audit failed: expected authenticated GET-only access")
        return 0
    finally:
        for gateway in gateways.values():
            try:
                os.killpg(gateway["process"].pid, signal.SIGTERM)
                gateway["process"].wait(timeout=10)
            except Exception:
                try:
                    os.killpg(gateway["process"].pid, signal.SIGKILL)
                except Exception:
                    pass
            gateway["log"].close()
            gateway["proxy"].shutdown()
            gateway["proxy"].server_close()
        try:
            os.killpg(fixture.pid, signal.SIGTERM)
            fixture.wait(timeout=5)
        except Exception:
            fixture.kill()
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
