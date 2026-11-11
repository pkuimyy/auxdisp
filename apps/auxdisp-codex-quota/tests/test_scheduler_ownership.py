"""Exercise the actual PowerShell bridge with Windows identity translation."""

import base64
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from auxdisp_codex_quota.scheduler import BRIDGE, MARKER, TaskScheduler
from auxdisp_codex_quota.paths import AppPaths
from auxdisp_codex_quota.service import ServiceController
from auxdisp_codex_quota.win32 import ServiceError, WindowsIPC, current_sid


@pytest.mark.parametrize("error,diagnostic", [
    ("TASK_IDENTITY_UNRESOLVED", "could not be resolved"),
    ("TASK_IDENTITY_MISMATCH", "different Windows user"),
    ("TASK_MARKER_MISMATCH", "management marker"),
    ("TASK_ACTION_MISMATCH", "entry point"),
])
def test_ownership_errors_have_distinct_safe_diagnostics(tmp_path, monkeypatch, error, diagnostic):
    monkeypatch.setattr("auxdisp_codex_quota.scheduler.system_directory", lambda: str(tmp_path))
    runner = Mock(return_value=SimpleNamespace(returncode=1, stdout=json.dumps({"error": error})))
    scheduler = TaskScheduler("S-1-5-21-test", runner)
    with pytest.raises(ServiceError, match=error) as caught:
        scheduler.call("delete")
    assert diagnostic in str(caught.value) and "no changes made" in str(caught.value)


# Only the COM transport is faked. Identity resolution and every ownership check
# execute the production BRIDGE, including refusal before the operation switch.
FAKE_COM = r"""
$fixture = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__FIXTURE__')) | ConvertFrom-Json
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
switch ($fixture.identity) {
    'sid' { $userId = $identity.User.Value }
    'username' { $userId = $env:USERNAME }
    'qualified' { $userId = $identity.Name }
    'different_sid' { $userId = 'S-1-5-18' }
    'different_name' {
        $userId = [Security.Principal.SecurityIdentifier]::new('S-1-5-18').Translate(
            [Security.Principal.NTAccount]).Value
    }
    'invalid_sid' { $userId = 'S-invalid' }
    'empty' { $userId = '' }
    default { $userId = $fixture.identity }
}
$actions = [pscustomobject]@{ Count = $fixture.count }
$actions | Add-Member ScriptMethod Item { param($index) return [pscustomobject]@{
    Arguments = $fixture.arguments; Path = 'C:\Python\pythonw.exe'
} }
$fixtureTask = [pscustomobject]@{
    Definition = [pscustomobject]@{
        Principal = [pscustomobject]@{ UserId = $userId }
        RegistrationInfo = [pscustomobject]@{ Description = $fixture.description }
        Actions = $actions
    }
    Enabled = $true; State = 3; LastTaskResult = 0
}
$folder = [pscustomobject]@{}
$folder | Add-Member ScriptMethod GetTask { param($name) return $fixtureTask }
$folder | Add-Member ScriptMethod DeleteTask { throw 'Mutation must have been rejected' }
$fakeScheduler = [pscustomobject]@{}
$fakeScheduler | Add-Member ScriptMethod Connect { }
$fakeScheduler | Add-Member ScriptMethod GetFolder { param($name) return $folder }
"""


@pytest.mark.skipif(os.name != "nt", reason="Native SID/account translation requires Windows")
@pytest.mark.parametrize("identity,description,count,arguments,error", [
    ("sid", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background --config test", None),
    ("username", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background --config test", None),
    ("qualified", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background --config test", None),
    ("different_sid", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background test",
     "TASK_IDENTITY_MISMATCH"),
    ("different_name", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background test",
     "TASK_IDENTITY_MISMATCH"),
    ("auxdisp-no-such-user-" + uuid.uuid4().hex, MARKER + " test", 1,
     "-I -m auxdisp_codex_quota._background test", "TASK_IDENTITY_UNRESOLVED"),
    ("invalid_sid", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background test",
     "TASK_IDENTITY_UNRESOLVED"),
    ("empty", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background test", "TASK_IDENTITY_UNRESOLVED"),
    ("username", "unrelated task", 1, "-I -m auxdisp_codex_quota._background test", "TASK_MARKER_MISMATCH"),
    ("username", None, 1, "-I -m auxdisp_codex_quota._background test", "TASK_MARKER_MISMATCH"),
    ("username", MARKER + " test", 0, "-I -m auxdisp_codex_quota._background test", "TASK_ACTION_MISMATCH"),
    ("username", MARKER + " test", 2, "-I -m auxdisp_codex_quota._background test", "TASK_ACTION_MISMATCH"),
    ("username", MARKER + " test", 1, "-I -m unrelated_module test", "TASK_ACTION_MISMATCH"),
    ("username", MARKER + " test", 1, "-I -m auxdisp_codex_quota._background_extra test",
     "TASK_ACTION_MISMATCH"),
    ("username", MARKER + " test", 1, None, "TASK_ACTION_MISMATCH"),
])
def test_bridge_normalizes_identity_and_rejects_unmanaged_tasks(
    tmp_path, identity, description, count, arguments, error,
):
    fixture = base64.b64encode(json.dumps(dict(
        identity=identity, description=description, count=count, arguments=arguments,
    )).encode()).decode()
    command = FAKE_COM.replace("__FIXTURE__", fixture) + BRIDGE.replace(
        "$scheduler = New-Object -ComObject 'Schedule.Service'", "$scheduler = $fakeScheduler",
    )
    payload = dict(operation="delete" if error else "query", name="unused-test-task", sid=current_sid(), marker=MARKER)
    script = tmp_path / "ownership-bridge.ps1"
    script.write_text(command, encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        input=json.dumps(payload), capture_output=True, encoding="utf-8", errors="replace", timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    response = json.loads(result.stdout.lstrip("\ufeff"))
    if error:
        assert result.returncode == 1 and response == {"error": error}, (response, result.stderr)
    else:
        assert result.returncode == 0 and response["registered"], (response, result.stderr)


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
