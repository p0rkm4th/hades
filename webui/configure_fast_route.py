"""Ensure the owner-visible Fast model uses the direct Hermes Compute route.

This is an idempotent Open WebUI database migration. Hermes Compute is an
OpenAI-compatible completion endpoint, not an Ollama endpoint, and it is
intentionally marked completion-only because its context/tool contract is not
qualified for Hermes Agent.
"""

import json
import os
import sqlite3


DB = "/app/backend/data/webui.db"
MODEL_ID = "qwen3:8b"
BASE_URL = os.environ.get("HADES_FAST_OPENAI_API_BASE_URL", "").strip().rstrip("/")
if BASE_URL and not BASE_URL.endswith("/v1"):
    BASE_URL += "/v1"


def configure() -> None:
    if not BASE_URL or not os.path.exists(DB):
        return
    db = sqlite3.connect(DB)
    try:
        def get(key):
            row = db.execute("select value from config where key = ?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

        def put(key, value):
            db.execute(
                "update config set value = ? where key = ?",
                (json.dumps(value, separators=(",", ":")), key),
            )

        ollama_urls = get("ollama.base_urls") or []
        ollama_configs = get("ollama.api_configs") or {}
        for config in ollama_configs.values():
            config["model_ids"] = [item for item in config.get("model_ids", []) if item != MODEL_ID]
        put("ollama.base_urls", ollama_urls)
        put("ollama.api_configs", ollama_configs)

        openai_urls = get("openai.api_base_urls") or []
        if BASE_URL not in openai_urls:
            openai_urls.append(BASE_URL)
        route_index = openai_urls.index(BASE_URL)
        openai_configs = get("openai.api_configs") or {}
        for config in openai_configs.values():
            config["model_ids"] = [item for item in config.get("model_ids", []) if item != MODEL_ID]
        config = openai_configs.setdefault(str(route_index), {"enable": True, "model_ids": [], "headers": {}})
        config["enable"] = True
        config["model_ids"] = sorted(set(config.get("model_ids", []) + [MODEL_ID]))
        config.setdefault("headers", {})
        put("openai.api_base_urls", openai_urls)
        put("openai.api_configs", openai_configs)

        updated = db.execute(
            "update model set base_model_id = NULL, name = ?, meta = ? where id = ?",
            (
                "Hades Fast (Hermes Compute)",
                json.dumps({
                    "description": "Direct conversational model on Hermes Compute; completion-only, HADES tools unavailable.",
                    "capabilities": {"builtin_tools": False},
                }, separators=(",", ":")),
                MODEL_ID,
            ),
        )
        if updated.rowcount == 0:
            db.rollback()
            return
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    configure()
