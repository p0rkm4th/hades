"""Read-only n8n adapter for the HADES automation projection."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contracts import AutomationError, N8NGateway


class N8NHttpError(AutomationError):
    """Runner unavailable or returned an invalid canonical response."""


class _NoRedirectHandler(HTTPRedirectHandler):
    """Never forward the API key to a redirect target."""

    def redirect_request(self, *_args: Any, **_kwargs: Any):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())


def urlopen(request: Request, *, timeout: float):
    """Open a metadata request without following redirects."""

    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


class N8NHttpGateway(N8NGateway):
    """Minimal n8n REST adapter; no local workflow or execution state."""

    WORKFLOW_LIMIT = 100

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 3.0):
        if not base_url or not api_key:
            raise ValueError("n8n base URL and API key are required")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("n8n base URL must be an HTTP(S) endpoint")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(query)}" if query else ""
        request = Request(
            f"{self.base_url}{path}{suffix}",
            headers={"Accept": "application/json", "X-N8N-API-KEY": self.api_key},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise N8NHttpError("n8n metadata request failed") from exc

    @staticmethod
    def _rows(payload: Any) -> list[Mapping[str, Any]]:
        rows = payload.get("data") if isinstance(payload, Mapping) else payload
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise N8NHttpError("n8n metadata response has invalid shape")
        return rows

    @staticmethod
    def _tag_values(raw: Mapping[str, Any], prefix: str) -> tuple[str, ...]:
        values = []
        for tag in raw.get("tags", ()):
            name = tag.get("name") if isinstance(tag, Mapping) else tag
            if isinstance(name, str) and name.startswith(prefix):
                value = name[len(prefix):].strip()
                if value:
                    values.append(value)
        return tuple(values)

    def list_workflows(self) -> tuple[Mapping[str, Any], ...]:
        result = []
        for row in self._rows(self._get("/api/v1/workflows", {"limit": self.WORKFLOW_LIMIT})):
            template = self._tag_values(row, "hades-template:")
            owners = self._tag_values(row, "hades-owner:")
            groups = self._tag_values(row, "hades-group:")
            triggers = self._tag_values(row, "hades-trigger:")
            approved = "true" in {value.lower() for value in self._tag_values(row, "hades-approved:")}
            template_id = template[0] if template else ""
            # n8n limits tag names to 24 characters; the live canary uses the
            # short `shw` tag and remains explicit rather than accepting any
            # user-defined template alias.
            template_id = {"shw": "server-health-watch", "bkp": "hades-backup-verification"}.get(template_id, template_id)
            result.append({
                "id": str(row.get("id", "")),
                "template_id": template_id,
                "owner": owners[0] if owners else "",
                "shared_groups": groups,
                "active": bool(row.get("active", False)),
                "trigger": triggers[0] if triggers else "",
                "next_run": row.get("nextRun"),
                "approved": approved,
            })
        return tuple(result)

    def list_executions(self, workflow_id: str, limit: int = 5) -> tuple[Mapping[str, Any], ...]:
        if not workflow_id or not 1 <= limit <= 100:
            raise ValueError("workflow ID and bounded execution limit are required")
        result = []
        for row in self._rows(self._get("/api/v1/executions", {"workflowId": workflow_id, "limit": limit})):
            execution_data = row.get("data", {})
            execution_id = row.get("id")
            if execution_id:
                try:
                    detail = self._get(f"/api/v1/executions/{execution_id}", {"includeData": "true"})
                    if isinstance(detail, Mapping):
                        execution_data = detail.get("data", execution_data)
                except N8NHttpError:
                    pass
            projected = {
                "startedAt": row.get("startedAt"),
                "status": str(row.get("status", row.get("finished", "unknown"))),
            }
            if row.get("id") is not None:
                projected["executionId"] = str(row.get("id"))
            # n8n execution payloads vary by version. Extract only the fixed
            # Server Health Watch projection; never expose arbitrary node data.
            def walk(value: Any) -> None:
                if isinstance(value, Mapping):
                    for key in ("hades_state", "hades_reason", "hades_transition", "hades_notification", "observed_state", "source", "observed_at", "freshness", "custody", "low", "out", "no_minimum"):
                        if key in value and key not in projected:
                            projected[key] = value[key]
                    for child in value.values():
                        walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)
            walk(execution_data)
            result.append(projected)
        return tuple(result)


class N8NControlHttpGateway(N8NHttpGateway):
    """Explicitly privileged adapter for one approved typed workflow family.

    This class is never used by the read-only inventory path. Its API key must
    be a separate n8n credential with only the selected workflow/control
    scopes, and callers must still perform HADES authorization and confirmation
    before invoking it.
    """

    def _mutate(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {
            "Accept": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", headers=headers, data=body, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise N8NHttpError("n8n control request failed") from exc
        if not isinstance(result, Mapping):
            raise N8NHttpError("n8n control response has invalid shape")
        return result

    def create_workflow(self, workflow: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = dict(workflow)
        payload.pop("id", None)
        payload.pop("active", None)
        payload.pop("tags", None)
        return self._mutate("POST", "/api/v1/workflows", payload)

    def update_workflow(self, workflow_id: str, workflow: Mapping[str, Any]) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        payload = dict(workflow)
        payload.pop("id", None)
        payload.pop("active", None)
        payload.pop("tags", None)
        return self._mutate("PUT", f"/api/v1/workflows/{workflow_id}", payload)

    def execute_workflow(self, workflow_id: str, webhook_path: str | None = None) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        # n8n's public API has no generic execute endpoint. The typed canary
        # owns a private webhook path equal to its opaque HADES automation ID;
        # this adapter never accepts a caller-supplied path or graph.
        return self._mutate("POST", f"/webhook/{webhook_path or workflow_id}", {})

    def set_workflow_active(self, workflow_id: str, active: bool) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        action = "activate" if active else "deactivate"
        return self._mutate("POST", f"/api/v1/workflows/{workflow_id}/{action}", {})

    def publish_workflow(self, workflow_id: str) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        return self._mutate("POST", f"/api/v1/workflows/{workflow_id}/publish", {})

    def unpublish_workflow(self, workflow_id: str) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        return self._mutate("POST", f"/api/v1/workflows/{workflow_id}/unpublish", {})

    def delete_workflow(self, workflow_id: str) -> Mapping[str, Any]:
        if not workflow_id:
            raise ValueError("workflow ID is required")
        return self._mutate("DELETE", f"/api/v1/workflows/{workflow_id}")
