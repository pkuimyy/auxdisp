"""Stable ownership diagnostics and explicit native Direct COM acceptance."""

import json
import os
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from auxdisp_codex_quota.scheduler import TaskScheduler
from auxdisp_codex_quota.paths import AppPaths
from auxdisp_codex_quota.service import ServiceController
from auxdisp_codex_quota.win32 import ServiceError, WindowsIPC, current_sid
from auxdisp_codex_quota.task_adapter import ARGUMENT_PREFIXES, MARKER, SchedulerError, validate_ownership
from auxdisp_codex_quota._scheduler_com_worker import resolve_identity


@pytest.mark.parametrize("error,diagnostic", [
    ("TASK_IDENTITY_UNRESOLVED", "could not be resolved"),
    ("TASK_IDENTITY_MISMATCH", "different Windows user"),
    ("TASK_MARKER_MISMATCH", "management marker"),
    ("TASK_ACTION_MISMATCH", "entry point"),
])
def test_ownership_errors_have_distinct_safe_diagnostics(tmp_path, monkeypatch, error, diagnostic):
    runner = Mock(return_value=SimpleNamespace(returncode=1, stdout=json.dumps({"error": error})))
    scheduler = TaskScheduler("S-1-5-21-test", runner)
    with pytest.raises(ServiceError, match=error) as caught:
        scheduler.call("delete")
    assert diagnostic in str(caught.value) and "no changes made" in str(caught.value)


@pytest.mark.parametrize("count,arguments", [
    (0, ARGUMENT_PREFIXES[0] + "test"), (2, ARGUMENT_PREFIXES[0] + "test"),
    (1, None), (1, ""), (1, "-I -m unrelated test"),
    (1, "-I -m auxdisp_codex_quota._background_extra test"),
    (1, "-E -m auxdisp_codex_quota._background test"),
    (1, "-E -P -m auxdisp_codex_quota._background_extra test"),
])
def test_invalid_action_formats_fail_closed(count, arguments):
    with pytest.raises(SchedulerError, match="TASK_ACTION_MISMATCH"):
        validate_ownership("user", MARKER + " test", count, arguments, "sid", lambda value: "sid")


@pytest.mark.skipif(os.name != "nt", reason="Native Windows identity API")
def test_runtime_identity_resolver_accepts_sid_local_and_qualified_name():
    import win32security

    sid = current_sid()
    name, domain, _ = win32security.LookupAccountSid(None, win32security.ConvertStringSidToSid(sid))
    for identity in (sid, name, domain + "\\" + name):
        assert resolve_identity(identity, win32security) == sid


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("AUXDISP_CODEX_QUOTA_REAL_TASK_TEST") != "1",
    reason="Opt-in Windows task registration and physical display test",
)
def test_real_registered_task_lifecycle_preserves_existing_task(tmp_path):
    """Register only a fresh task, run synthetic data, and remove only that task.

    Uses the installed interpreter and real IPC/COM, never calls codex-auth.
    The background host may access the physical display and writes normal user
    diagnostic state/logs. Refuse to run alongside an existing display instance.
    """
    existing = TaskScheduler()
    before = existing.query()
    ipc = WindowsIPC()
    if ipc.running() or before.get("state") in (2, 4):
        pytest.fail("Stop the existing instance explicitly before opting into this test")
    scheduler = TaskScheduler()
    scheduler.name = existing.name + "-ownership-test-" + uuid.uuid4().hex
    assert scheduler.query() == {"registered": False}
    paths = AppPaths(tmp_path / "task-profile")
    paths.root.mkdir(parents=True)
    paths.config.write_text(
        "[collector]\nexecutable = '" + sys.executable + "'\nrefresh_seconds = 3\n",
        encoding="utf-8",
    )
    # Collector runs `python list --api --json` in this task's working directory.
    (paths.root / "list").write_text(
        "from importlib.resources import files\n"
        "print(files('auxdisp_codex_quota').joinpath('data/demo.json').read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )
    controller = ServiceController(scheduler=scheduler, ipc=ipc, paths=paths)
    try:
        started = controller.execute("start", paths.config)
        assert started["registered"] and started["process_running"]
        assert controller.execute("status")["process_running"]
        assert controller.execute("start", paths.config)["process_running"]
        stopped = controller.execute("stop")
        assert not stopped["process_running"] and not stopped["enabled"]
        assert not stopped["stop_result"]["forced"]
        restarted = controller.execute("restart", paths.config)
        assert restarted["process_running"] and restarted["enabled"]
        removed = controller.execute("uninstall-service")
        assert not removed["registered"] and not removed["process_running"]
        assert not removed["stop_result"]["forced"]
    finally:
        # Never delete, disable, start, or rewrite the pre-existing task.
        if scheduler.query().get("registered"):
            controller.execute("uninstall-service")
        deadline = time.monotonic() + 5
        while ipc.running() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not ipc.running()
        assert existing.query() == before
