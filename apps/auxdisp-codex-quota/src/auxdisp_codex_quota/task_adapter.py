"""Backend-neutral task contract, ownership policy, and safe errors."""

import json
import logging
from typing import Protocol

from .paths import APP_ID
from .win32 import ServiceError


MARKER = f"{APP_ID} managed background task v1"
ARGUMENT_PREFIXES = ("-I -m auxdisp_codex_quota._background ", "-E -P -m auxdisp_codex_quota._background ")
OPERATIONS = frozenset(("query", "register", "enable", "disable", "run", "end", "delete"))
OWNERSHIP_ERRORS = {
    "TASK_IDENTITY_UNRESOLVED": "Task principal could not be resolved to a SID",
    "TASK_IDENTITY_MISMATCH": "Task principal belongs to a different Windows user",
    "TASK_MARKER_MISMATCH": "Task description does not contain the expected management marker",
    "TASK_ACTION_MISMATCH": "Task actions do not match the managed background entry point",
}


class TaskSchedulerAdapter(Protocol):
    """query returns an owned snapshot including XML for in-memory rollback.

    call supports OPERATIONS; register accepts disabled XML. Every operation
    validates existing ownership before any mutation. end stops only this task.
    No backend automatically falls back to another transport.
    """

    sid: str
    name: str

    def query(self) -> dict: ...

    def call(self, operation: str, **values) -> dict: ...


def default_scheduler(sid):
    """One backend only; failures never trigger an alternate execution path."""
    from .direct_com import DirectComTaskScheduler
    return DirectComTaskScheduler(sid)


class SchedulerError(ServiceError):
    def __init__(self, kind, operation, stage, **codes):
        self.kind, self.operation, self.stage = kind, operation, stage
        self.codes = {key: value for key, value in codes.items() if type(value) is int}
        metadata = " ".join(f"{key}={value}" for key, value in self.codes.items())
        detail = OWNERSHIP_ERRORS.get(kind)
        super().__init__(f"{kind}: Task Scheduler {operation} failed during {stage}"
                         f"{(' ' + metadata) if metadata else ''}"
                         f"{('; ' + detail + '; no changes made') if detail else ''}; no elevation was attempted")


def validate_ownership(identity, description, count, arguments, sid, resolve):
    """Shared fail-closed policy; resolver uses the platform's identity APIs."""
    try:
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("Empty principal")
        principal = resolve(identity)
    except Exception:
        raise SchedulerError("TASK_IDENTITY_UNRESOLVED", "ownership", "resolve_identity") from None
    if principal != sid:
        raise SchedulerError("TASK_IDENTITY_MISMATCH", "ownership", "compare_identity")
    if not isinstance(description, str) or not description.startswith(MARKER + " "):
        raise SchedulerError("TASK_MARKER_MISMATCH", "ownership", "marker")
    if count != 1 or not isinstance(arguments, str) or not arguments.startswith(ARGUMENT_PREFIXES):
        raise SchedulerError("TASK_ACTION_MISMATCH", "ownership", "actions")


def decode_response(result, operation):
    """Stable, safe errors from the isolated Python COM worker."""
    logging.debug("Task Scheduler operation=%s exit_code=%s stdout_chars=%d stderr_chars=%d",
                  operation, result.returncode, len(result.stdout), len(getattr(result, "stderr", "")))
    try:
        response = json.loads(result.stdout.lstrip("\ufeff"))
        if not isinstance(response, dict):
            raise ValueError("Invalid response")
    except ValueError:
        kind = "PROCESS_EXIT_FAILED" if result.returncode else "INVALID_BRIDGE_RESPONSE"
        raise SchedulerError(kind, operation, "response_parse", exit_code=result.returncode) from None
    if result.returncode or "error" in response:
        error = response.get("error")
        if isinstance(error, str) and error in OWNERSHIP_ERRORS:
            raise SchedulerError(error, operation, "ownership")
        if error == "TASK_OWNERSHIP_MISMATCH":
            raise ServiceError("Task name is occupied by an unmanaged task; no changes made")
        if error == "TASK_SCHEDULER_FAILED":
            code, scode = response.get("code"), response.get("scode")
            denied = any(type(value) is int and value & 0xFFFFFFFF == 0x80070005 for value in (code, scode))
            phase = response.get("stage")
            stage = phase if phase in ("create_com", "connect", "get_root", "get_task", "ownership",
                                       "task_operation", "initialize_com", "validate_spec") else "com_bridge"
            raise SchedulerError("ACCESS_DENIED" if denied else "COM_CALL_FAILED", operation, stage,
                                 hresult=code, scode=scode, exit_code=result.returncode)
        if error in ("COM_UNAVAILABLE", "INVALID_REQUEST", "INVALID_TASK_SPEC"):
            raise SchedulerError(error, operation, "request")
        kind = "PROCESS_EXIT_FAILED" if result.returncode else "INVALID_BRIDGE_RESPONSE"
        raise SchedulerError(kind, operation, "bridge_result", exit_code=result.returncode)
    return response
