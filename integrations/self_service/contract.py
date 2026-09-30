"""Plan-first, bounded household workload requests.

This module deliberately does not contact Proxmox. It validates the product
contract that must sit in front of a constrained provisioner: approved
templates, quotas, ownership, sharing, preview, and confirmation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,63}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")

TEMPLATES = {
    "minecraft": {"cores": 4, "memory_mib": 8192, "disk_gib": 40},
    "website": {"cores": 1, "memory_mib": 1024, "disk_gib": 10},
    "linux-sandbox": {"cores": 2, "memory_mib": 4096, "disk_gib": 30},
}


def _id(value: Any, label: str) -> str:
    value = str(value or "").strip()
    if not _ID.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class WorkloadRequest:
    request_id: str
    owner: str
    template: str
    name: str
    cores: int
    memory_mib: int
    disk_gib: int
    shared_with: tuple[str, ...] = ()


class SelfServicePolicy:
    """Validate synthetic requests without granting raw hypervisor authority."""

    def __init__(self, quotas: dict[str, dict[str, int]] | None = None):
        self.quotas = quotas or {
            "max_workloads": 2,
            "max_cores": 8,
            "max_memory_mib": 16384,
            "max_disk_gib": 120,
        }
        self._requests: dict[str, WorkloadRequest] = {}

    def plan(self, actor: str, request_id: str, template: str, name: str, *, shared_with: tuple[str, ...] = ()) -> dict[str, Any]:
        actor = _id(actor, "actor")
        request_id = _id(request_id, "request_id")
        template = str(template or "").strip().lower()
        if template not in TEMPLATES:
            return {"status": "FAILED", "error": "workload template is not approved", "writes_performed": False}
        if not isinstance(name, str) or not _NAME.fullmatch(name.strip()):
            return {"status": "FAILED", "error": "workload name is invalid", "writes_performed": False}
        if request_id in self._requests:
            existing = self._requests[request_id]
            return {"status": "ALREADY_PLANNED", "request": asdict(existing), "writes_performed": False}
        try:
            shares = tuple(dict.fromkeys(_id(value, "share target") for value in shared_with))
        except ValueError as exc:
            return {"status": "FAILED", "error": str(exc), "writes_performed": False}
        spec = TEMPLATES[template]
        owned = [r for r in self._requests.values() if r.owner == actor]
        if len(owned) >= self.quotas["max_workloads"]:
            return {"status": "FAILED", "error": "workload quota exceeded", "writes_performed": False}
        if sum(r.cores for r in owned) + spec["cores"] > self.quotas["max_cores"]:
            return {"status": "FAILED", "error": "CPU quota exceeded", "writes_performed": False}
        if sum(r.memory_mib for r in owned) + spec["memory_mib"] > self.quotas["max_memory_mib"]:
            return {"status": "FAILED", "error": "memory quota exceeded", "writes_performed": False}
        if sum(r.disk_gib for r in owned) + spec["disk_gib"] > self.quotas["max_disk_gib"]:
            return {"status": "FAILED", "error": "disk quota exceeded", "writes_performed": False}
        request = WorkloadRequest(request_id, actor, template, name.strip(), spec["cores"], spec["memory_mib"], spec["disk_gib"], shares)
        return {"status": "PREVIEW", "request": asdict(request), "writes_performed": False, "confirmation_required": True}

    def confirm(self, actor: str, request: WorkloadRequest) -> dict[str, Any]:
        actor = _id(actor, "actor")
        if request.owner != actor:
            return {"status": "DENIED", "error": "only the workload owner may confirm creation", "writes_performed": False}
        if request.template not in TEMPLATES:
            return {"status": "FAILED", "error": "workload template is not approved", "writes_performed": False}
        if request.request_id in self._requests:
            return {"status": "ALREADY_PLANNED", "request": asdict(self._requests[request.request_id]), "writes_performed": False}
        self._requests[request.request_id] = request
        return {"status": "READY_FOR_CONSTRAINED_PROVISIONER", "request": asdict(request), "writes_performed": False}

    def can_manage(self, actor: str, request_id: str) -> bool:
        actor = _id(actor, "actor")
        request = self._requests.get(_id(request_id, "request_id"))
        return bool(request and (request.owner == actor or actor in request.shared_with))

    def confirmed_request(self, request_id: str) -> WorkloadRequest | None:
        """Return only a request that crossed the owner confirmation boundary."""
        return self._requests.get(_id(request_id, "request_id"))

    def export(self) -> dict[str, Any]:
        return {"version": 1, "requests": [asdict(request) for request in self._requests.values()]}
