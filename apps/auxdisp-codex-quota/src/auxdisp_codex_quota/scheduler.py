"""Stable task-management entry point; Python Direct COM is the sole backend."""

from .direct_com import DirectComTaskScheduler as TaskScheduler
from .task_adapter import MARKER as MARKER
from .task_spec import NS as NS, TaskSpec as TaskSpec

__all__ = ["TaskScheduler", "MARKER", "NS", "TaskSpec"]
