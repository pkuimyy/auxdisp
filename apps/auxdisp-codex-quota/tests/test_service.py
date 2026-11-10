"""Lifecycle acceptance with a fake scheduler and isolated synthetic processes."""

from contextlib import contextmanager
import base64
from datetime import datetime, timezone
import json
import logging
import os
import subprocess
import sys
from threading import Event, Thread
import time
from types import SimpleNamespace
from unittest.mock import Mock
import uuid
from xml.etree import ElementTree as ET

import pytest

from auxdisp_codex_quota import cli
from auxdisp_codex_quota import _background as background
from auxdisp_codex_quota.collector import CollectionWorker, Collector
from auxdisp_codex_quota.config import Settings, load_settings
from auxdisp_codex_quota.display import DisplayWorker, FileAdapter
from auxdisp_codex_quota.host import HealthWriter, file_logging, run_host
from auxdisp_codex_quota.model import DataError
from auxdisp_codex_quota.paths import AppPaths, select_config
from auxdisp_codex_quota.render import Renderer
from auxdisp_codex_quota.runtime import Runtime
from auxdisp_codex_quota.scheduler import BRIDGE, MARKER, NS, TaskScheduler, TaskSpec
from auxdisp_codex_quota.service import ServiceController, read_state, write_state
from auxdisp_codex_quota.win32 import InstanceBusy, ServiceError, WindowsIPC, current_sid


class FakeIPC:
    sid = "S-1-5-21-test-user"

    def __init__(self, events):
        self.events = events
        self.active = False
        self.wedged = False
        self.stop = Event()

    @contextmanager
    def lock(self, suffix="instance", timeout=0):
        yield

    @contextmanager
    def stop_event(self):
        yield self.stop

    def running(self):
        return self.active

    def signal_stop(self):
        self.events.append("signal")
        if not self.wedged:
            self.active = False
        return True


class FakeScheduler:
    name = "auxdisp-codex-quota-S-1-5-21-test-user"

    def __init__(self, ipc, events):
        self.ipc, self.events = ipc, events
        self.task = {"registered": False}

    def query(self):
        return dict(self.task, state=4 if self.ipc.active and self.task["registered"] else 3)

    def call(self, operation, **values):
        self.events.append(operation)
        if operation == "register":
            root = ET.fromstring(values["xml"])
            self.task = {"registered": True, "enabled": True,
                         "description": root.findtext(f"{{{NS}}}RegistrationInfo/{{{NS}}}Description"),
                         "python": root.findtext(f"{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}Command")}
        elif operation == "run":
            self.ipc.active = True
        elif operation in ("enable", "disable"):
            self.task["enabled"] = operation == "enable"
        elif operation == "end":
            self.ipc.active = False
        elif operation == "delete":
            self.task = {"registered": False}
        return {}


@pytest.fixture
def managed(tmp_path, monkeypatch):
    events = []
    ipc = FakeIPC(events)
    scheduler = FakeScheduler(ipc, events)
    python = tmp_path / "installed Python/pythonw.exe"
    executable = tmp_path / "native command/codex-auth.exe"
    for path in (python, executable):
        path.parent.mkdir(parents=True)
        path.write_bytes(b"test path; not executed")
    monkeypatch.setattr("auxdisp_codex_quota.service.resolve_executable", lambda name: str(executable))
    paths = AppPaths(tmp_path / "app data")
    tick = [0.0]

    def sleep(seconds):
        tick[0] += seconds

    controller = ServiceController(scheduler, ipc, paths, clock=lambda: tick[0], sleep=sleep,
                                   start_timeout=1, stop_timeout=1,
                                   spec_factory=lambda sid, config, exe, cwd: TaskSpec(sid, python, config, exe, cwd))
    return controller, events, ipc, scheduler


def test_first_start_repeat_start_stop_restart_and_uninstall(managed):
    controller, events, ipc, scheduler = managed
    first = controller.execute("start")
    assert first["registered"] and first["enabled"] and first["process_running"]
    assert controller.paths.config.is_file()
    controller.execute("start")
    assert events.count("register") == events.count("run") == 1
    before_stop = len(events)
    stopped = controller.execute("stop")
    assert events[before_stop:before_stop + 2] == ["disable", "signal"]
    assert not stopped["enabled"] and not stopped["process_running"]
    assert not stopped["stop_result"]["forced"]
    controller.execute("stop")  # safe with no live process
    controller.execute("restart")
    assert ipc.active and scheduler.task["enabled"]
    removed = controller.execute("uninstall-service")
    assert not removed["registered"] and not removed["process_running"]
    assert controller.paths.config.exists()  # personal configuration is retained


def test_environment_upgrade_stops_old_instance_then_updates_one_task(managed):
    controller, events, ipc, scheduler = managed
    controller.execute("start")
    scheduler.task["python"] = str(controller.paths.root / "removed-install/pythonw.exe")
    baseline = len(events)
    controller.execute("start")
    operations = events[baseline:]
    assert operations.index("disable") < operations.index("signal") < operations.index("register")
    assert events.count("register") == 2 and events.count("run") == 2
    assert ipc.active


def test_registration_policy_failure_does_not_enable_or_run_a_task(managed, monkeypatch):
    controller, events, _, scheduler = managed
    original = scheduler.call

    def denied(operation, **values):
        if operation == "register":
            raise ServiceError("Task registration denied by current-user policy; no elevation attempted")
        return original(operation, **values)

    monkeypatch.setattr(scheduler, "call", denied)
    with pytest.raises(ServiceError, match="no elevation"):
        controller.execute("start")
    assert "run" not in events and "enable" not in events


def test_package_upgrade_restarts_existing_task_without_duplicate_registration(managed, monkeypatch):
    controller, events, _, scheduler = managed
    controller.execute("start")
    name = scheduler.name
    monkeypatch.setattr("auxdisp_codex_quota.scheduler.__version__", "0.2.0")
    baseline = len(events)
    assert controller.execute("start")["process_running"]
    assert scheduler.name == name
    operations = events[baseline:]
    assert operations.index("disable") < operations.index("register") < operations.index("run")
    assert events.count("register") == 2


def test_restart_after_crash_keeps_one_registration(managed):
    controller, events, ipc, _ = managed
    controller.execute("start")
    ipc.active = False
    assert not controller.execute("status")["process_running"]
    assert controller.execute("start")["process_running"]
    assert events.count("register") == 1 and events.count("run") == 2


def test_start_reuses_resolved_command_when_later_shell_lacks_path(managed, monkeypatch):
    controller, events, _, _ = managed
    controller.execute("start")

    def missing(name):
        raise DataError("COMMAND_NOT_FOUND")

    monkeypatch.setattr("auxdisp_codex_quota.service.resolve_executable", missing)
    assert controller.execute("start")["process_running"]
    assert events.count("run") == 1
    controller.paths.config.write_text('[collector]\nexecutable="a-different-command"', encoding="utf-8")
    with pytest.raises(DataError, match="COMMAND_NOT_FOUND"):
        controller.execute("start")


def test_stop_timeout_ends_only_managed_task_and_records_abnormal_stop(managed):
    controller, events, ipc, _ = managed
    controller.execute("start")
    ipc.wedged = True
    result = controller.execute("stop")
    assert result["stop_result"]["forced"] and not result["enabled"]
    assert events.index("disable") < events.index("signal") < events.index("end")
    assert read_state(controller.paths.state.parent / "last-stop.json")["forced"]
    controller.execute("status")
    assert events.count("run") == 1  # disabled task remains stopped


def test_unmanaged_foreground_timeout_never_kills_a_pid(managed):
    controller, events, ipc, _ = managed
    ipc.active = ipc.wedged = True
    with pytest.raises(ServiceError, match="no scheduled task"):
        controller.execute("stop")
    assert "end" not in events and "delete" not in events


def test_status_distinguishes_registration_enablement_liveness_and_stale_health(managed):
    controller, _, ipc, scheduler = managed
    write_state(controller.paths.state, {"pid": os.getpid(), "heartbeat": time.time(),
                                        "phase": "running", "usb_connected": True,
                                        "last_success_at": "2026-11-10T12:00:00+00:00"})
    status = controller.execute("status")
    assert not status["registered"] and not status["process_running"] and status["usb_connected"] is None
    controller.execute("start")
    scheduler.task["enabled"] = False
    status = controller.execute("status")
    assert status["registered"] and not status["enabled"] and status["process_running"]
    assert status["usb_connected"] is True
    write_state(controller.paths.state, {"heartbeat": time.time() - 60, "usb_connected": True})
    assert controller.execute("status")["usb_connected"] is None
    ipc.active = False  # a stale PID/JSON file cannot prove a living process
    assert not controller.execute("status")["process_running"]


def test_task_xml_defines_current_user_logon_bounded_recovery_and_absolute_paths(tmp_path):
    spec = TaskSpec("S-1-5-21-123", tmp_path / 'Python & Unicode 中文/pythonw.exe',
                    tmp_path / 'app data/config.toml', tmp_path / 'commands/codex-auth.exe', tmp_path)
    root = ET.fromstring(spec.xml())
    ns = {"t": NS}
    assert root.findtext("t:Principals/t:Principal/t:UserId", namespaces=ns) == spec.sid
    assert root.findtext("t:Principals/t:Principal/t:LogonType", namespaces=ns) == "InteractiveToken"
    assert root.findtext("t:Principals/t:Principal/t:RunLevel", namespaces=ns) == "LeastPrivilege"
    assert root.findtext("t:Triggers/t:LogonTrigger/t:UserId", namespaces=ns) == spec.sid
    for field, value in {
        "MultipleInstancesPolicy": "IgnoreNew", "ExecutionTimeLimit": "PT0S",
        "DisallowStartIfOnBatteries": "false", "StopIfGoingOnBatteries": "false",
        "StartWhenAvailable": "true", "IdleSettings/StopOnIdleEnd": "false",
        "RestartOnFailure/Interval": "PT1M", "RestartOnFailure/Count": "3",
    }.items():
        target = "t:Settings/" + "/".join("t:" + part for part in field.split("/"))
        assert root.findtext(target, namespaces=ns) == value
    assert root.findtext("t:Actions/t:Exec/t:Command", namespaces=ns) == str(spec.python)
    arguments = root.findtext("t:Actions/t:Exec/t:Arguments", namespaces=ns)
    assert arguments.startswith("-I -m auxdisp_codex_quota._background ")
    assert str(spec.config) in arguments and str(spec.executable) in arguments
    assert root.findtext("t:Actions/t:Exec/t:WorkingDirectory", namespaces=ns) == str(tmp_path)
    assert MARKER in spec.description


def test_scheduler_transport_is_hidden_json_and_does_not_echo_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("auxdisp_codex_quota.scheduler.system_directory", lambda: str(tmp_path))
    runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"registered":false}'))
    scheduler = TaskScheduler("S-1-5-21-test", runner)
    scheduler.call("register", xml='<Task>quotes \' " $() & 中文</Task>')
    options = runner.call_args.kwargs
    command = runner.call_args.args[0]
    assert "-WindowStyle" in command and "Hidden" in command and "-EncodedCommand" in command
    assert "xml" in json.loads(options["input"])
    assert "quotes" not in " ".join(command)
    runner.return_value = SimpleNamespace(returncode=1, stdout='{"error":"TASK_SCHEDULER_FAILED","code":5}')
    with pytest.raises(ServiceError, match="no elevation"):
        scheduler.query()
    runner.return_value = SimpleNamespace(returncode=1, stdout='{"error":"TASK_OWNERSHIP_MISMATCH"}')
    with pytest.raises(ServiceError, match="unmanaged task"):
        scheduler.call("delete")
    runner.return_value = SimpleNamespace(returncode=1, stdout="PRIVATE_CREDENTIAL_RESPONSE")
    with pytest.raises(ServiceError) as exc:
        scheduler.query()
    assert "PRIVATE_CREDENTIAL_RESPONSE" not in str(exc.value)


def test_configuration_priority_ignores_launch_directory(tmp_path, monkeypatch):
    paths = AppPaths.current()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text("invalid working-directory config", encoding="utf-8")
    assert select_config() is None
    assert load_settings(select_config()) == Settings()
    paths.root.mkdir(parents=True)
    paths.config.write_text("[display]\nbrightness=41", encoding="utf-8")
    assert select_config() == paths.config
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("[display]\nbrightness=62", encoding="utf-8")
    assert load_settings(select_config(explicit)).brightness == 62


def test_cli_management_never_collects_accounts_or_opens_usb(monkeypatch, capsys):
    controller = Mock()
    controller.execute.return_value = {"registered": True, "process_running": True}
    monkeypatch.setattr(cli, "ServiceController", lambda: controller)
    monkeypatch.setattr(cli, "Collector", lambda *a: pytest.fail("real collector accessed"))
    monkeypatch.setattr(cli, "DisplayWorker", lambda *a: pytest.fail("USB accessed"))
    for command in ("start", "stop", "status", "restart", "uninstall-service"):
        assert cli.main([command]) == 0
        controller.execute.assert_called_with(command, None)
    assert '"registered": true' in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["start", "--demo"])


def test_runtime_stop_cancels_active_collection_and_closes_virtual_display(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "list").write_text("import time; time.sleep(30)", encoding="utf-8")
    collector = Collector(sys.executable, timeout=30)
    worker = CollectionWorker(collector)
    output = DisplayWorker(FileAdapter(tmp_path / "latest.png"))
    runtime = Runtime(Settings(), worker, Renderer(Settings()), output)
    stop = Event()
    thread = Thread(target=runtime.run, kwargs={"stop_event": stop})
    thread.start()
    process = None
    try:
        deadline = time.monotonic() + 5
        while process is None and time.monotonic() < deadline:
            with collector._lock:
                process = collector._process
            time.sleep(0.01)
        assert process is not None
        stop.set()
        thread.join(8)
        assert not thread.is_alive() and process.poll() is not None
        assert not worker.thread.is_alive() and not output.thread.is_alive()
    finally:
        stop.set()
        collector.close()
        thread.join(8)


def test_host_health_is_anonymous_and_records_graceful_shutdown(tmp_path, document):
    collector = cli.FixtureCollector()
    output = DisplayWorker(FileAdapter(tmp_path / "latest.png"))
    runtime = Runtime(Settings(), CollectionWorker(collector), Renderer(Settings()), output)
    ipc, paths = FakeIPC([]), AppPaths(tmp_path / "profile")
    run_host(runtime, 0.25, paths=paths, ipc=ipc, background=True)
    state = read_state(paths.state)
    assert state["phase"] == "stopped" and state["cleanup_complete"]
    assert state["usb_connected"] is False
    assert state["last_success_at"] is not None
    serialized = paths.state.read_text(encoding="utf-8")
    assert "work@example.com" not in serialized and "demo-dual" not in serialized
    assert not output.thread.is_alive() and not runtime.collector.thread.is_alive()


def test_duplicate_host_cleans_workers_without_starting_collection(tmp_path):
    ipc = FakeIPC([])

    @contextmanager
    def busy(*args, **kwargs):
        raise InstanceBusy("already running")
        yield

    ipc.lock = busy
    collector = Mock()
    output = Mock()
    runtime = Runtime(Settings(), collector, Renderer(Settings()), output)
    with pytest.raises(InstanceBusy):
        run_host(runtime, paths=AppPaths(tmp_path), ipc=ipc)
    collector.request.assert_not_called()
    collector.close.assert_called_once()
    output.close.assert_called_once()


def test_health_retains_last_success_across_idle_restart(tmp_path):
    paths = AppPaths(tmp_path)
    stamp = datetime.now(timezone.utc).isoformat()
    write_state(paths.state, {"last_success_at": stamp})
    runtime = Runtime(Settings(), Mock(), Renderer(Settings()), Mock(usb_connected=False))
    HealthWriter(paths, "background").update(runtime)
    assert read_state(paths.state)["last_success_at"] == stamp


def test_file_logs_rotate_and_close_handlers(tmp_path):
    paths = AppPaths(tmp_path)
    root = logging.getLogger()
    before = list(root.handlers)
    with file_logging(paths, "INFO"):
        handler = root.handlers[-1]
        assert handler.maxBytes == 1024 * 1024 and handler.backupCount == 3
        handler.maxBytes = 128
        for _ in range(30):
            logging.info("Synthetic lifecycle message")
    assert list(root.handlers) == before and handler.stream is None
    assert len(list(paths.log.parent.glob("service.log*"))) <= 4


def test_private_background_entry_runs_synthetic_io_and_closes_logs(tmp_path, monkeypatch):
    config = tmp_path / "settings.toml"
    config.write_text("", encoding="utf-8")
    paths = AppPaths.current()
    monkeypatch.setattr(background, "Collector", lambda *args: cli.FixtureCollector())
    monkeypatch.setattr(background, "DisplayAdapter", lambda *args: FileAdapter(tmp_path / "background.png"))
    monkeypatch.setattr(background, "run_host", lambda runtime, **kwargs: run_host(
        runtime, 0.25, ipc=FakeIPC([]), **kwargs,
    ))
    assert background.main(["--config", str(config), "--executable", sys.executable]) == 0
    assert (tmp_path / "background.png").exists()
    assert read_state(paths.state)["cleanup_complete"] is True
    text = paths.log.read_text(encoding="utf-8")
    assert "resources released" in text and "work@example.com" not in text


def test_private_background_entry_masks_config_failure(tmp_path, monkeypatch):
    config = tmp_path / "settings.toml"
    config.write_text("PRIVATE_CONFIG_TOKEN", encoding="utf-8")
    assert background.main(["--config", str(config), "--executable", sys.executable]) == 1
    text = AppPaths.current().log.read_text(encoding="utf-8")
    assert "PRIVATE_CONFIG_TOKEN" not in text and "Background host failed" in text


@pytest.mark.skipif(os.name != "nt", reason="Win32 primitives require Windows")
def test_real_named_mutex_and_stop_event_across_processes():
    namespace = "pytest-" + uuid.uuid4().hex
    code = """
import sys
from auxdisp_codex_quota.win32 import WindowsIPC
ipc = WindowsIPC(sys.argv[1])
with ipc.lock():
    with ipc.stop_event() as stop:
        print('READY', flush=True)
        assert stop.wait(10)
print('STOPPED', flush=True)
"""
    process = subprocess.Popen([sys.executable, "-c", code, namespace], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    ipc = WindowsIPC(namespace)
    try:
        assert process.stdout.readline().strip() == "READY"
        assert ipc.running()
        with pytest.raises(InstanceBusy):
            with ipc.lock():
                pytest.fail("duplicate instance admitted")
        assert ipc.signal_stop()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert "STOPPED" in stdout and not ipc.running()
    finally:
        if process.poll() is None:
            process.kill()  # only this test's Popen child
            process.communicate(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell syntax validation requires Windows")
def test_fixed_scheduler_bridge_is_valid_powershell(tmp_path):
    script = tmp_path / "bridge.ps1"
    script.write_text(BRIDGE, encoding="utf-8-sig")
    command = ("$errors = $null; $tokens = $null; "
               "[void][System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$errors); "
               "if ($errors.Count) { exit 1 }")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                             "& { " + command + " }", str(script)], capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Native Task Scheduler XML parsing requires Windows")
def test_task_xml_is_accepted_by_native_com_without_registering_any_task(tmp_path):
    spec = TaskSpec(current_sid(), tmp_path / "pythonw.exe", tmp_path / "config.toml",
                    tmp_path / "codex-auth.exe", tmp_path)
    command = """
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$definition = $scheduler.NewTask(0)
$definition.XmlText = [Console]::In.ReadToEnd()
exit 0
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(command.encode("utf-16-le")).decode("ascii")],
        input=spec.xml(), capture_output=True, encoding="utf-8", errors="replace", timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Read-only scheduler integration requires Windows")
def test_real_scheduler_bridge_queries_a_missing_unique_task_without_registration():
    scheduler = TaskScheduler()
    scheduler.name += "-pytest-" + uuid.uuid4().hex
    assert scheduler.query() == {"registered": False}
