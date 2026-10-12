"""Compatibility imports for the shared coding-workspace sandbox."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.workspace_sandbox import WorkspaceSandboxUnavailable, run_isolated_workspace  # noqa: E402,F401

__all__ = ["WorkspaceSandboxUnavailable", "run_isolated_workspace"]
