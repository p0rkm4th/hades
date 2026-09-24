#!/usr/bin/env python3
"""Tiny OpenAI-compatible backend for the isolated application fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time

MODEL = "synthetic-reconstruction-model"


def _tool_call(name, arguments):
    return {
        "id": f"synthetic-call-{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, sort_keys=True)},
    }


def _response_for(request):
    user_messages = [
        str(message.get("content", ""))
        for message in request.get("messages", [])
        if message.get("role") == "user"
    ]
    prompt = user_messages[-1].lower() if user_messages else ""
    if any(message.get("role") == "tool" for message in request.get("messages", [])):
        return {"content": "Synthetic continuation: sources remain distinct and no write was performed."}
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
        return {"tool_calls": [_tool_call("mcp_grocy_stock_overview_tool", {})]}
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
        content = body["choices"][0]["message"]["content"]
        created = body["created"]
        for chunk in (
            {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
            },
            {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ):
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


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
