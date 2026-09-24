"""Constrained adapter boundary for approved self-service workloads."""

from __future__ import annotations

from typing import Any, Callable

from .contract import SelfServicePolicy


class ConstrainedProvisioner:
    """Call only an approved executor with policy-owned placement and inputs."""

    def __init__(self, policy: SelfServicePolicy, executor: Callable[..., dict[str, Any]], placements: dict[str, dict[str, int]]):
        self.policy = policy
        self.executor = executor
        self.placements = {str(template).lower(): dict(target) for template, target in placements.items()}
        self._outcomes: dict[str, dict[str, Any]] = {}

    def provision(self, actor: str, request_id: str) -> dict[str, Any]:
        request = self.policy.confirmed_request(request_id)
        if request is None:
            return {"status": "FAILED", "error": "workload is not owner-confirmed", "writes_performed": False}
        if request.owner != actor:
            return {"status": "DENIED", "error": "only the workload owner may create this workload", "writes_performed": False}
        if request_id in self._outcomes:
            return dict(self._outcomes[request_id])
        target = self.placements.get(request.template)
        if target is None:
            return {"status": "FAILED", "error": "no approved placement exists for this workload", "writes_performed": False}
        result = self.executor(
            request.template,
            target=dict(target),
            name=request.name,
            cores=request.cores,
            memory_mib=request.memory_mib,
            disk_gib=request.disk_gib,
            owner_confirmed=True,
        )
        if not isinstance(result, dict):
            result = {"status": "OUTCOME UNKNOWN", "error": "provisioner returned an invalid result", "writes_performed": True, "retry": False}
        if result.get("status") in {"SUCCEEDED", "FAILED", "OUTCOME UNKNOWN"}:
            self._outcomes[request_id] = dict(result)
        return result
