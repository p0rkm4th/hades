"""Small parsers for checking Hindsight's configured worker identity."""
from __future__ import annotations

from typing import Any


def configured_worker_id(compose_config: dict[str, Any]) -> str:
    service = compose_config.get("services", {}).get("hindsight", {})
    environment = service.get("environment", {})
    if isinstance(environment, list):
        environment = dict(item.split("=", 1) for item in environment if "=" in item)
    value = environment.get("HINDSIGHT_API_WORKER_ID", "") if isinstance(environment, dict) else ""
    return str(value).strip()


def running_worker_id(container_inspect: dict[str, Any] | list[dict[str, Any]]) -> str:
    container = container_inspect[0] if isinstance(container_inspect, list) and container_inspect else container_inspect
    environment = container.get("Config", {}).get("Env", []) if isinstance(container, dict) else []
    for item in environment:
        if item.startswith("HINDSIGHT_API_WORKER_ID="):
            return item.partition("=")[2].strip()
    return ""


def worker_identity_matches(compose_config: dict[str, Any], container_inspect: dict[str, Any] | list[dict[str, Any]]) -> bool:
    expected = configured_worker_id(compose_config)
    actual = running_worker_id(container_inspect)
    return bool(expected and actual and expected == actual)
