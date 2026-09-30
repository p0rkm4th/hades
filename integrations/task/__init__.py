"""Durable, policy-neutral coordination state for HADES goals.

The Task layer owns coordination state only.  Canonical household, finance,
homelab, memory, and automation systems remain authoritative for their own
data and execution.
"""

from .store import (
    ApprovalError,
    AuthorityError,
    ConcurrencyError,
    ExecutionError,
    TaskError,
    TaskStore,
    TaskStatus,
)
from .n8n_wait import build_wait_workflow, fixed_wait_contract, wait_workflow_id

__all__ = [
    "ApprovalError",
    "AuthorityError",
    "ConcurrencyError",
    "ExecutionError",
    "TaskError",
    "TaskStore",
    "TaskStatus",
    "build_wait_workflow",
    "fixed_wait_contract",
    "wait_workflow_id",
]
