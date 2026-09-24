"""Durable authorization metadata for HADES-managed workloads.

Proxmox remains the runtime source of truth. This file contains only the
minimum ownership/grant metadata needed to decide who may manage a workload;
it is not a VM inventory, state cache, or user-data store.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .contract import _id


class WorkloadRegistry:
    def __init__(self, path: str | None = None):
        configured = path or os.environ.get("HADES_SELF_SERVICE_REGISTRY_FILE", "").strip()
        if not configured:
            raise ValueError("self-service registry path is not configured")
        self.path = Path(configured)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "workloads": {}}
        if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
            raise ValueError("self-service registry must be a private regular file")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("workloads"), dict):
            raise ValueError("self-service registry is invalid")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".workloads.", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def register(self, resource_id: str, *, owner: str, node: str, vmid: int, template: str, name: str) -> dict[str, Any]:
        resource_id = _id(resource_id, "resource_id")
        owner = _id(owner, "owner")
        node = _id(node, "node")
        template = _id(template, "template")
        name = str(name or "").strip()
        if not name or len(name) > 64 or not isinstance(vmid, int) or isinstance(vmid, bool):
            raise ValueError("invalid workload metadata")
        data = self._read()
        existing = data["workloads"].get(resource_id)
        if existing is not None and existing != {
            "owner": owner, "node": node, "vmid": vmid, "template": template,
            "name": name, "shared_with": [],
        }:
            raise ValueError("workload identity is already registered")
        data["workloads"][resource_id] = {
            "owner": owner, "node": node, "vmid": vmid, "template": template,
            "name": name, "shared_with": sorted(set(existing.get("shared_with", []) if existing else [])),
        }
        self._write(data)
        return {"status": "READY", "resource_id": resource_id, "writes_performed": True}

    def list_for(self, actor: str) -> list[dict[str, Any]]:
        actor = _id(actor, "actor")
        return [dict(item, resource_id=resource_id) for resource_id, item in self._read()["workloads"].items()
                if item.get("owner") == actor or actor in item.get("shared_with", [])]

    def grant(self, actor: str, resource_id: str, grantee: str) -> dict[str, Any]:
        actor = _id(actor, "actor")
        resource_id = _id(resource_id, "resource_id")
        grantee = _id(grantee, "grantee")
        data = self._read()
        item = data["workloads"].get(resource_id)
        if item is None:
            return {"status": "NOT_FOUND", "writes_performed": False}
        if item.get("owner") != actor:
            return {"status": "DENIED", "error": "only the workload owner may share it", "writes_performed": False}
        item["shared_with"] = sorted(set(item.get("shared_with", [])) | {grantee})
        self._write(data)
        return {"status": "READY", "resource_id": resource_id, "writes_performed": True}

    def revoke(self, actor: str, resource_id: str, grantee: str) -> dict[str, Any]:
        actor = _id(actor, "actor")
        resource_id = _id(resource_id, "resource_id")
        grantee = _id(grantee, "grantee")
        data = self._read()
        item = data["workloads"].get(resource_id)
        if item is None:
            return {"status": "NOT_FOUND", "writes_performed": False}
        if item.get("owner") != actor:
            return {"status": "DENIED", "error": "only the workload owner may revoke access", "writes_performed": False}
        item["shared_with"] = [value for value in item.get("shared_with", []) if value != grantee]
        self._write(data)
        return {"status": "READY", "resource_id": resource_id, "writes_performed": True}

    def can_manage(self, actor: str, resource_id: str) -> bool:
        actor = _id(actor, "actor")
        resource_id = _id(resource_id, "resource_id")
        item = self._read()["workloads"].get(resource_id)
        return bool(item and (item.get("owner") == actor or actor in item.get("shared_with", [])))

    def remove(self, actor: str, resource_id: str) -> dict[str, Any]:
        actor = _id(actor, "actor")
        resource_id = _id(resource_id, "resource_id")
        data = self._read()
        item = data["workloads"].get(resource_id)
        if item is None:
            return {"status": "NOT_FOUND", "writes_performed": False}
        if item.get("owner") != actor:
            return {"status": "DENIED", "error": "only the workload owner may remove it", "writes_performed": False}
        del data["workloads"][resource_id]
        self._write(data)
        return {"status": "READY", "resource_id": resource_id, "writes_performed": True}
