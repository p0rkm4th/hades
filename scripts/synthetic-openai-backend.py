#!/usr/bin/env python3
"""Tiny OpenAI-compatible backend for the isolated application fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import json
import sys
import time

MODEL = "synthetic-reconstruction-model"
HINDSIGHT_FACT = "The synthetic user prefers violet comet-42 markers."
HINDSIGHT_FACT_RESPONSE = json.dumps({
    "facts": [{
        "what": HINDSIGHT_FACT,
        "when": "N/A",
        "where": "N/A",
        "who": "user",
        "why": "Explicit synthetic acceptance fact.",
        "fact_type": "world",
        "entities": ["user", "violet comet-42 markers"],
    }],
})


def _tool_call(name, arguments):
    return {
        "id": f"synthetic-call-{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, sort_keys=True)},
    }


def _configured_tool_call(request, suffix, arguments):
    """Use the exact function name Hermes exposed for this request."""
    candidates = [
        row.get("function", {}).get("name", "")
        for row in request.get("tools", [])
        if isinstance(row, dict)
    ]
    matches = [name for name in candidates if name.endswith(suffix)]
    if len(matches) != 1:
        if os.environ.get("HADES_SYNTHETIC_BACKEND_TRACE_TOOLS") == "1":
            print("synthetic-model available tool names: " + json.dumps(candidates), file=sys.stderr, flush=True)
        return {"content": "That Grocy action is not available in this session; nothing was changed."}
    return {"tool_calls": [_tool_call(matches[0], arguments)]}


def _response_for(request):
    user_messages = [
        str(message.get("content", ""))
        for message in request.get("messages", [])
        if message.get("role") == "user"
    ]
    prompt = user_messages[-1].lower() if user_messages else ""
    messages = request.get("messages", [])
    tool_messages = [message for message in messages if message.get("role") == "tool"]
    if tool_messages:
        called_tools = [
            str(call.get("function", {}).get("name", ""))
            for message in messages
            for call in message.get("tool_calls", [])
        ]
        result = str(tool_messages[-1].get("content", "")).strip()
        if any(name.endswith("stock_overview_tool") for name in called_tools) and "pantry" in prompt:
            if result.casefold() == "no stock found.":
                return {"content": "Grocy's current stock check found no items in the pantry. I didn't change anything."}
            return {"content": "Grocy's current pantry result: " + result}
        if any(name.endswith("shopping_list_add_tool") for name in called_tools):
            return {"content": "Grocy returned this result for the shopping-list request: " + result}
        if any(name.endswith("shopping_list_view_tool") for name in called_tools):
            return {"content": "Grocy's current shopping-list result: " + result}
        return {"content": "Synthetic continuation: the connected tool returned its result; no additional action was taken."}
    if "online" in prompt and "pantry" in prompt:
        return {"tool_calls": [
            _tool_call("web_search", {"query": "synthetic tomatoes basil recipe"}),
            _tool_call("mcp_grocy_stock_overview_tool", {}),
            _tool_call("hindsight_recall", {"query": "Beta dislikes mushrooms"}),
        ]}
    if "online" in prompt or "recipe online" in prompt:
        return {"tool_calls": [_tool_call("web_search", {"query": "synthetic tomatoes basil recipe"})]}
    if "private memory" in prompt or "dislike" in prompt:
        return {"tool_calls": [_tool_call("hindsight_recall", {"query": "Beta dislikes mushrooms"})]}
    if "pantry" in prompt:
        return _configured_tool_call(request, "stock_overview_tool", {})
    if "shopping list" in prompt and "add" in prompt and "hades synthetic milk" in prompt:
        return _configured_tool_call(request, "shopping_list_add_tool", {
            "product": "HADES Synthetic Milk", "amount": 1,
        })
    if "shopping list" in prompt and any(term in prompt for term in ("what's on", "what is on", "show me")):
        return _configured_tool_call(request, "shopping_list_view_tool", {})
    if "preview" in prompt and "serving" in prompt:
        return {"tool_calls": [_tool_call("recipe_set_servings", {"recipe": "mushroom-free pasta", "servings": 4})]}
    if "delegate" in prompt or "agent zero" in prompt:
        return {"tool_calls": [_tool_call("agent_zero_delegate", {"task": "synthetic read-only service status"})]}
    return {"content": "Synthetic application response: " + (user_messages[-1] if user_messages else "")}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send(self, body, status=200):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_stream(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        message = body["choices"][0]["message"]
        created = body["created"]
        deltas = []
        if message.get("tool_calls"):
            deltas.append({"role": "assistant"})
            for index, tool_call in enumerate(message["tool_calls"]):
                deltas.append({
                    "tool_calls": [{
                        "index": index,
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"],
                        },
                    }],
                })
            finish_reason = "tool_calls"
        else:
            deltas = [{"role": "assistant", "content": message.get("content", "")}]
            finish_reason = "stop"

        chunks = [
            {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            for delta in deltas
        ]
        chunks.append({
            "id": body["id"],
            "object": "chat.completion.chunk",
            "created": created,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        })
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/v1/models":
            self._send({"data": [{"id": MODEL, "object": "model", "owned_by": "synthetic"}]})
            return
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/api/chat":
            # Hindsight's pinned Ollama provider uses this endpoint. The
            # reconstruction fixture answers with one fixed synthetic fact;
            # it never records or interprets the submitted prompt.
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self._send({
                "model": MODEL,
                "message": {"role": "assistant", "content": HINDSIGHT_FACT_RESPONSE},
                "done": True,
            })
            return
        if self.path != "/v1/chat/completions":
            self._send({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        generated = _response_for(request)
        user = next(
            (message.get("content", "") for message in request.get("messages", [])
             if message.get("role") == "user"),
            "",
        )
        message = {"role": "assistant"}
        if "tool_calls" in generated:
            message["tool_calls"] = generated["tool_calls"]
        else:
            message["content"] = generated["content"]
        response = {
            "id": "synthetic-reconstruction-completion",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }],
        }
        if request.get("stream"):
            self._send_stream(response)
        else:
            self._send(response)


bind_host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
ThreadingHTTPServer((bind_host, bind_port), Handler).serve_forever()
