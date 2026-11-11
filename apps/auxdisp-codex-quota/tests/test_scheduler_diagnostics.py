"""Classify transport failures without executing PowerShell or echoing output."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from auxdisp_codex_quota.scheduler import TaskScheduler
from auxdisp_codex_quota.win32 import ServiceError


@pytest.mark.parametrize("failure,kind", [
    (PermissionError(13, "PRIVATE credential/path"), "PROCESS_START_FAILED"),
    (FileNotFoundError(2, "PRIVATE path"), "PROCESS_START_FAILED"),
    (subprocess.TimeoutExpired(["PRIVATE command"], 20, output="PRIVATE token"), "PROCESS_TIMEOUT"),
    (SimpleNamespace(returncode=0, stdout="PRIVATE invalid", stderr="PRIVATE"), "INVALID_BRIDGE_RESPONSE"),
    (SimpleNamespace(returncode=0, stdout="[]", stderr="PRIVATE"), "INVALID_BRIDGE_RESPONSE"),
    (SimpleNamespace(returncode=7, stdout="PRIVATE invalid", stderr="PRIVATE"), "PROCESS_EXIT_FAILED"),
    (SimpleNamespace(returncode=9, stdout="{}", stderr="PRIVATE"), "PROCESS_EXIT_FAILED"),
    (SimpleNamespace(returncode=1, stdout=json.dumps({"error": "TASK_SCHEDULER_FAILED", "code": 0x80070005}),
                     stderr="PRIVATE"), "ACCESS_DENIED"),
    (SimpleNamespace(returncode=1, stdout=json.dumps({"error": "TASK_SCHEDULER_FAILED", "code": -2147024891}),
                     stderr="PRIVATE"), "ACCESS_DENIED"),
    (SimpleNamespace(returncode=1, stdout=json.dumps({"error": "TASK_SCHEDULER_FAILED", "code": 0x800706BA}),
                     stderr="PRIVATE"), "COM_CALL_FAILED"),
    (SimpleNamespace(returncode=1, stdout=json.dumps({"error": "TASK_SCHEDULER_FAILED", "code": "PRIVATE"}),
                     stderr="PRIVATE"), "COM_CALL_FAILED"),
    (SimpleNamespace(returncode=1, stdout='{"error": ["PRIVATE"]}', stderr="PRIVATE"), "PROCESS_EXIT_FAILED"),
])
def test_failures_are_safe_distinct_and_never_retried(tmp_path, monkeypatch, caplog, failure, kind):
    runner = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    with caplog.at_level("DEBUG"):
        with pytest.raises(ServiceError, match=kind) as caught:
            TaskScheduler("test-user", runner).query()
    assert "PRIVATE" not in str(caught.value) + caplog.text
    assert "POLICY_RESTRICTED" not in str(caught.value)
    assert "no elevation" in str(caught.value)
    assert runner.call_count == 1
