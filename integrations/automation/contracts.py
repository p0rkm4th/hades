"""HADES-owned automation view/control contracts over an external n8n runner.

This module deliberately stores no schedule database and starts no background
work. n8n remains canonical for workflow and execution state. The in-memory
gateway exists only for contract tests and disposable dogfood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence


AUTOMATION_SCHEMA = "hades-automation/v1"
ACTIONS = ("inspect", "run", "pause", "resume", "edit", "delete")
READ_ONLY_RESOURCES = frozenset({
    "grocy.household",
    "uptime_kuma.household",
    "hades-core.health",
    "backup.evidence",
})


class AutomationError(ValueError):
    """Expected, user-facing automation contract failure."""


class ApprovalRequired(AutomationError):
    """The workflow has not passed the product approval gate."""


@dataclass(frozen=True)
class AutomationTemplate:
    template_id: str
    name: str
    purpose: str
    trigger_kinds: tuple[str, ...]
    resources: tuple[str, ...]
    read_only: bool
    minimum_interval_minutes: int
    maximum_interval_minutes: int
    allowed_groups: tuple[str, ...]
    notification_mode: str
    failure_behavior: str
    approved: bool = False

    def validate_interval(self, minutes: int) -> None:
        if not self.minimum_interval_minutes <= minutes <= self.maximum_interval_minutes:
            raise AutomationError(
                f"schedule must be between {self.minimum_interval_minutes} and "
                f"{self.maximum_interval_minutes} minutes"
            )


class TemplateCatalog:
    """Small explicit catalog; this is not a free-form workflow generator."""

    def __init__(self, templates: Sequence[AutomationTemplate] | None = None):
        items = tuple(templates or self.default_templates())
        for item in items:
            if item.read_only and not set(item.resources).issubset(READ_ONLY_RESOURCES):
                raise AutomationError("read-only template contains an unsupported resource")
        self._templates = {item.template_id: item for item in items}

    @staticmethod
    def default_templates() -> tuple[AutomationTemplate, ...]:
        return (
            AutomationTemplate(
                "server-health-watch", "Server Health Watch",
                "Notify when an authorized server changes to offline.",
                ("interval", "event"), ("uptime_kuma.household", "hades-core.health"), True,
                5, 1440, ("hades-owner", "hades-household"), "state_change",
                "deduplicate_same_state", True,
            ),
            AutomationTemplate(
                "backup-verification", "Backup Verification",
                "Report only when the accepted backup evidence is missing or failed.",
                ("interval",), ("backup.evidence",), True,
                60, 10080, ("hades-owner",), "failure_only",
                "outcome_unknown_without_evidence", False,
            ),
            AutomationTemplate(
                "weekly-household-summary", "Weekly Household Summary",
                "Summarize authorized household inventory and shared service status.",
                ("weekly",), ("grocy.household", "uptime_kuma.household", "backup.evidence"), True,
                10080, 10080, ("hades-owner",), "weekly",
                "label_partial_sources", False,
            ),
            AutomationTemplate(
                "low-inventory-summary", "Low Inventory Summary",
                "Report current Grocy low-stock items at execution time.",
                ("interval", "weekly"), ("grocy.household",), True,
                1440, 10080, ("hades-owner",), "state_change",
                "label_dependency_unavailable", False,
            ),
        )

    def get(self, template_id: str) -> AutomationTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise AutomationError("unsupported automation template") from exc

    def all(self) -> tuple[AutomationTemplate, ...]:
        return tuple(self._templates.values())


@dataclass(frozen=True)
class AutomationView:
    """Safe user-facing projection of an n8n workflow and latest execution."""

    schema: str
    automation_id: str
    template_id: str
    name: str
    purpose: str
    owner: str
    shared_groups: tuple[str, ...]
    status: str
    trigger: str
    last_run: str | None
    last_result: str | None
    next_run: str | None
    allowed_actions: tuple[str, ...]
    resources: tuple[str, ...]
    approved: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "purpose": self.purpose,
            "owner": self.owner,
            "shared_groups": list(self.shared_groups),
            "status": self.status,
            "trigger": self.trigger,
            "last_run": self.last_run,
            "last_result": self.last_result,
            "next_run": self.next_run,
            "allowed_actions": list(self.allowed_actions),
            "resources": list(self.resources),
            "approved": self.approved,
        }


@dataclass(frozen=True)
class AutomationSubject:
    user: str
    groups: frozenset[str] = frozenset()
    owner: bool = False


@dataclass(frozen=True)
class AutomationPolicy:
    """Operation-time policy; workflow sharing never grants resource access."""

    def can_view(self, subject: AutomationSubject, owner: str, shared_groups: Sequence[str]) -> bool:
        return subject.owner or subject.user == owner or bool(subject.groups.intersection(shared_groups))

    def allowed_actions(
        self,
        subject: AutomationSubject,
        owner: str,
        shared_groups: Sequence[str],
        *,
        read_only: bool,
        approved: bool,
    ) -> tuple[str, ...]:
        if not self.can_view(subject, owner, shared_groups):
            return ()
        if not approved:
            return ("inspect",)
        if subject.owner or subject.user == owner:
            return ACTIONS if not read_only else ("inspect", "run", "pause", "resume", "delete")
        return ("inspect", "run") if read_only else ("inspect",)

    def authorize_action(self, subject: AutomationSubject, view: AutomationView, action: str) -> None:
        if action not in ACTIONS or action not in view.allowed_actions:
            raise AutomationError("automation action is not authorized")
        if action in {"pause", "resume", "edit", "delete"} and not subject.owner and subject.user != view.owner:
            raise AutomationError("automation control requires its owner")


class N8NGateway(Protocol):
    """Minimal canonical boundary; implementations must not create schedules."""

    def list_workflows(self) -> Sequence[Mapping[str, Any]]: ...
    def list_executions(self, workflow_id: str, limit: int = 5) -> Sequence[Mapping[str, Any]]: ...


class N8NControlGateway(N8NGateway, Protocol):
    """Optional control surface implemented only by an approved runner adapter."""

    def execute_workflow(self, workflow_id: str, webhook_path: str | None = None) -> Mapping[str, Any]: ...
    def set_workflow_active(self, workflow_id: str, active: bool) -> Mapping[str, Any]: ...
    def delete_workflow(self, workflow_id: str) -> Mapping[str, Any]: ...


def _latest_execution(gateway: N8NGateway, workflow_id: str) -> Mapping[str, Any] | None:
    executions = list(gateway.list_executions(workflow_id, limit=1))
    return executions[0] if executions else None


class AutomationService:
    """Read-only inventory and preview facade over canonical n8n state."""

    def __init__(self, gateway: N8NGateway, catalog: TemplateCatalog | None = None, policy: AutomationPolicy | None = None):
        self.gateway = gateway
        self.catalog = catalog or TemplateCatalog()
        self.policy = policy or AutomationPolicy()

    def inventory(self, subject: AutomationSubject) -> tuple[AutomationView, ...]:
        views = []
        for workflow in self.gateway.list_workflows():
            try:
                template = self.catalog.get(str(workflow.get("template_id", "")))
            except AutomationError:
                # n8n may contain workflows owned by other projects. They are
                # not HADES automations and must not fail or leak into this
                # projection.
                continue
            owner = str(workflow.get("owner", ""))
            shared = tuple(str(item) for item in workflow.get("shared_groups", ()))
            if not self.policy.can_view(subject, owner, shared):
                continue
            execution = _latest_execution(self.gateway, str(workflow["id"]))
            approved = bool(workflow.get("approved", template.approved))
            actions = self.policy.allowed_actions(
                subject, owner, shared, read_only=template.read_only, approved=approved
            )
            views.append(AutomationView(
                AUTOMATION_SCHEMA, str(workflow["id"]), template.template_id,
                template.name, template.purpose, owner, shared,
                "active" if workflow.get("active") else "paused",
                str(workflow.get("trigger", "")),
                execution.get("startedAt") if execution else None,
                execution.get("status") if execution else None,
                workflow.get("next_run"), actions, template.resources,
                approved,
            ))
        return tuple(views)

    def preview(self, subject: AutomationSubject, template_id: str, *, interval_minutes: int, resources: Sequence[str]) -> dict[str, Any]:
        template = self.catalog.get(template_id)
        if not subject.owner and not set(subject.groups).intersection(template.allowed_groups):
            raise AutomationError("automation template is not available to this subject")
        if not set(resources).issubset(set(template.resources)):
            raise AutomationError("requested resource is outside the template allowlist")
        if not template.read_only:
            raise ApprovalRequired("write-capable automation requires explicit product approval")
        template.validate_interval(interval_minutes)
        return {
            "schema": AUTOMATION_SCHEMA,
            "template_id": template.template_id,
            "name": template.name,
            "purpose": template.purpose,
            "trigger": {"kind": "interval", "interval_minutes": interval_minutes},
            "resources": list(resources),
            "read_only": True,
            "notification_mode": template.notification_mode,
            "failure_behavior": template.failure_behavior,
            "requires_confirmation": True,
            "runner": "n8n",
        }

    def control(self, subject: AutomationSubject, automation_id: str, action: str, *, confirmed: bool) -> Mapping[str, Any]:
        """Apply one bounded control action after fresh visibility and confirmation."""
        if not confirmed:
            raise AutomationError("automation control requires explicit confirmation")
        current = {view.automation_id: view for view in self.inventory(subject)}
        view = current.get(automation_id)
        if view is None:
            raise AutomationError("automation is not visible to this subject")
        self.policy.authorize_action(subject, view, action)
        gateway = self.gateway
        if action == "run" and hasattr(gateway, "execute_workflow"):
            return gateway.execute_workflow(automation_id)  # type: ignore[attr-defined]
        if action == "pause" and hasattr(gateway, "set_workflow_active"):
            return gateway.set_workflow_active(automation_id, False)  # type: ignore[attr-defined]
        if action == "resume" and hasattr(gateway, "set_workflow_active"):
            return gateway.set_workflow_active(automation_id, True)  # type: ignore[attr-defined]
        if action == "delete" and hasattr(gateway, "delete_workflow"):
            return gateway.delete_workflow(automation_id)  # type: ignore[attr-defined]
        raise AutomationError("runner control action is unavailable")


class InMemoryN8NGateway:
    """Disposable canonical fixture for contract and DOM preparation tests."""

    def __init__(self, workflows: Sequence[Mapping[str, Any]] = (), executions: Mapping[str, Sequence[Mapping[str, Any]]] | None = None):
        self.workflows = [dict(item) for item in workflows]
        self.executions = {key: [dict(row) for row in value] for key, value in (executions or {}).items()}

    def list_workflows(self) -> Sequence[Mapping[str, Any]]:
        return tuple(self.workflows)

    def list_executions(self, workflow_id: str, limit: int = 5) -> Sequence[Mapping[str, Any]]:
        return tuple(self.executions.get(workflow_id, ()))[:limit]

    def execute_workflow(self, workflow_id: str) -> Mapping[str, Any]:
        if not any(row.get("id") == workflow_id for row in self.workflows):
            raise AutomationError("unknown workflow")
        self.executions.setdefault(workflow_id, []).insert(0, {"startedAt": "synthetic", "status": "queued"})
        return {"workflowId": workflow_id, "status": "queued"}

    def set_workflow_active(self, workflow_id: str, active: bool) -> Mapping[str, Any]:
        for row in self.workflows:
            if row.get("id") == workflow_id:
                row["active"] = active
                return {"id": workflow_id, "active": active}
        raise AutomationError("unknown workflow")

    def delete_workflow(self, workflow_id: str) -> Mapping[str, Any]:
        before = len(self.workflows)
        self.workflows[:] = [row for row in self.workflows if row.get("id") != workflow_id]
        if len(self.workflows) == before:
            raise AutomationError("unknown workflow")
        self.executions.pop(workflow_id, None)
        return {"id": workflow_id, "deleted": True}
