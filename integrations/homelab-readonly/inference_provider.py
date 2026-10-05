"""Bounded read-only model catalog protocols for inference providers."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin


_TIMEOUT_SECONDS = 4
_MAX_RESPONSE_BYTES = 512 * 1024
_MAX_MODELS = 512


def _bounded_catalog(payload: dict, key: str, description: str) -> list:
    values = payload.get(key)
    if not isinstance(values, list) or len(values) > _MAX_MODELS:
        raise ValueError(f"inference {description} has an invalid shape")
    return values


def read_provider_catalog(
    endpoint: dict[str, str],
    fetch: Callable[..., dict],
) -> dict:
    """Read one endpoint's provider-native catalog and optional residency.

    The caller owns endpoint configuration, credentials, TLS policy, fetch
    implementation, source identity, and error presentation. This module only
    shapes bounded provider GET responses; it never submits inference requests.
    """
    base = endpoint["url"].rstrip("/") + "/"
    provider = endpoint["provider"]
    token_file = endpoint["token_file"]
    ca_file = endpoint["ca_file"]

    def get(path: str) -> dict:
        return fetch(
            urljoin(base, path), token_file, ca_file,
            timeout_seconds=_TIMEOUT_SECONDS,
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )

    if provider == "openai-compatible":
        catalog = _bounded_catalog(
            get("v1/models"), "data", "model catalog",
        )
        models = [
            {"name": row["id"][:256]}
            for row in catalog
            if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]
        ]
        return {"models": models, "loaded_models": [], "loaded_status": "UNSUPPORTED"}

    if provider != "ollama":
        raise ValueError("inference provider is unsupported")

    catalog = _bounded_catalog(get("api/tags"), "models", "model catalog")
    models = []
    for row in catalog:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            continue
        models.append({
            "name": row["name"][:256],
            "size_bytes": row.get("size") if type(row.get("size")) is int and row["size"] >= 0 else None,
            "modified_at": str(row.get("modified_at") or "")[:64] or None,
        })

    try:
        running = _bounded_catalog(get("api/ps"), "models", "residency response")
        loaded = [
            {
                "name": row["name"][:256],
                "size_vram_bytes": row.get("size_vram") if type(row.get("size_vram")) is int and row["size_vram"] >= 0 else None,
            }
            for row in running
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        ]
        loaded_status = "CURRENT"
    except Exception:
        loaded, loaded_status = [], "UNKNOWN"

    return {"models": models, "loaded_models": loaded, "loaded_status": loaded_status}
