"""Bounded HADES view/control contracts for an external n8n runner."""

from .contracts import (
    ACTIONS,
    AUTOMATION_SCHEMA,
    AutomationPolicy,
    AutomationService,
    AutomationSubject,
    AutomationTemplate,
    AutomationView,
    InMemoryN8NGateway,
    N8NControlGateway,
    TemplateCatalog,
)
from .n8n_http import N8NControlHttpGateway, N8NHttpError, N8NHttpGateway
from .health_watch import (
    HEALTH_STATES,
    HealthSource,
    HealthWatchAuthorizationError,
    HealthWatchError,
    HealthWatchNotFound,
    HealthWatchService,
    HealthWatchSpec,
    HealthWatchStore,
    build_n8n_workflow,
)
from .backup_verification import BACKUP_STATES, BACKUP_TARGETS, BackupObservation, BackupTarget, BackupVerificationService, BackupVerificationSpec, build_n8n_workflow as build_backup_n8n_workflow, verify_all, verify_target, notification_transition
from .inventory_summary import GrocyReadUnavailable, InventoryObservation, InventorySummaryService, build_n8n_workflow as build_inventory_n8n_workflow, read_current_grocy_stock, render_summary, summarize_grocy
from .weekly_summary import SummaryHistory, build_n8n_workflow as build_weekly_n8n_workflow, compose_summary
from .lifecycle import LifecycleError, LifecycleStore, PHASE2_TEMPLATES, StagingAdapter, TypedLifecycle, TypedTemplate, UnknownMutation

__all__ = [
    "ACTIONS",
    "AUTOMATION_SCHEMA",
    "AutomationPolicy",
    "AutomationService",
    "AutomationSubject",
    "AutomationTemplate",
    "AutomationView",
    "InMemoryN8NGateway",
    "N8NControlGateway",
    "N8NHttpError",
    "N8NHttpGateway",
    "N8NControlHttpGateway",
    "HEALTH_STATES",
    "HealthSource",
    "HealthWatchAuthorizationError",
    "HealthWatchError",
    "HealthWatchNotFound",
    "HealthWatchService",
    "HealthWatchSpec",
    "HealthWatchStore",
    "build_n8n_workflow",
    "TemplateCatalog",
    "BACKUP_STATES", "BACKUP_TARGETS", "BackupObservation", "BackupTarget", "BackupVerificationService", "BackupVerificationSpec", "build_backup_n8n_workflow", "verify_all", "verify_target", "notification_transition",
    "GrocyReadUnavailable", "InventoryObservation", "InventorySummaryService", "build_inventory_n8n_workflow", "read_current_grocy_stock", "render_summary", "summarize_grocy", "SummaryHistory", "build_weekly_n8n_workflow", "compose_summary",
    "LifecycleError", "LifecycleStore", "PHASE2_TEMPLATES", "StagingAdapter", "TypedLifecycle", "TypedTemplate", "UnknownMutation",
]
