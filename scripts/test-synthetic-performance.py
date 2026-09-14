#!/usr/bin/env python3
"""Measure bounded synthetic web and recipe turns without real integrations."""

import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("HADES_OLLAMA_URL", "http://127.0.0.1:11434/v1").rstrip("/")
MODEL = os.environ.get("HADES_OLLAMA_MODEL", "qwen3:8b")
MAX_TOKENS = int(os.environ.get("HADES_PERF_MAX_TOKENS", "400"))
TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search current external information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "recipe_set_servings", "description": "Preview a recipe serving change; never apply without confirmation.", "parameters": {"type": "object", "properties": {"recipe": {"type": "string"}, "servings": {"type": "integer"}}, "required": ["recipe", "servings"]}}},
]


def model_call(messages):
    payload = {"model": MODEL, "messages": messages, "tools": TOOLS, "tool_choice": "auto", "stream": False, "max_tokens": MAX_TOKENS, "temperature": 0}
    request = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=180) as response:
        choice = json.load(response)["choices"][0]
    return choice, (time.perf_counter() - started) * 1000


def synthetic_tool(name, arguments):
    started = time.perf_counter()
    if name == "web_search":
        result = {"title": "Synthetic mushroom-free pasta", "snippet": "A pasta recipe using tomatoes and basil."}
    elif name == "recipe_set_servings":
        result = {"outcome": "PREVIEW", "recipe": arguments.get("recipe"), "servings": arguments.get("servings")}
    else:
        raise AssertionError(f"unexpected tool: {name}")
    return result, (time.perf_counter() - started) * 1000


def run(label, prompt, expected):
    messages = [{"role": "system", "content": "Use web_search for current external facts. For recipe serving changes, call recipe_set_servings only to produce a PREVIEW; never claim a write."}, {"role": "user", "content": prompt}]
    total_started = time.perf_counter()
    first, model_ms = model_call(messages)
    message = first.get("message", {})
    calls = message.get("tool_calls", [])
    names = [call.get("function", {}).get("name") for call in calls]
    if names != [expected]:
        raise SystemExit(f"{label}: expected [{expected}], got {names}")
    messages.append(message)
    tool_started = time.perf_counter()
    for call in calls:
        args = json.loads(call.get("function", {}).get("arguments", "{}"))
        result, _ = synthetic_tool(expected, args)
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    tool_ms = (time.perf_counter() - tool_started) * 1000
    _, continuation_ms = model_call(messages)
    total_ms = (time.perf_counter() - total_started) * 1000
    return {"workflow": label, "model_ms": round(model_ms, 1), "tool_ms": round(tool_ms, 1), "continuation_ms": round(continuation_ms, 1), "total_ms": round(total_ms, 1)}


def main():
    results = [run("web", "Find a recipe online using tomatoes and basil.", "web_search"), run("recipe", "Preview changing the mushroom-free pasta recipe to 4 servings.", "recipe_set_servings")]
    print(json.dumps({"model": MODEL, "results": results}, sort_keys=True))
    print("PASS synthetic performance capture")


if __name__ == "__main__":
    main()
