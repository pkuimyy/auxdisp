"""One contract for both transports; native COM and PowerShell are mocked."""

from copy import deepcopy
from contextlib import contextmanager
import io
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from xml.etree import ElementTree as ET

import pytest
import auxdisp_codex_quota
from importlib.resources import files

from auxdisp_codex_quota import _scheduler_com_worker as worker
from auxdisp_codex_quota.direct_com import DirectComTaskScheduler
from auxdisp_codex_quota.scheduler import NS, TaskScheduler, TaskSpec
from auxdisp_codex_quota.paths import AppPaths
from auxdisp_codex_quota.service import LifecycleError, ServiceController
from auxdisp_codex_quota.task_adapter import ARGUMENT_PREFIXES, SchedulerError, default_scheduler


SID = "S-1-5-21-123-1001"


def test_direct_com_is_the_only_default_backend():
    assert type(default_scheduler(SID)) is DirectComTaskScheduler
    assert TaskScheduler is DirectComTaskScheduler


def test_installed_runtime_has_no_shell_scheduler_backend():
    import auxdisp_codex_quota.scheduler as entry

    assert not hasattr(entry, "BRIDGE")
    root = files(auxdisp_codex_quota)
    for module in root.iterdir():
        if module.name.endswith(".py"):
            source = module.read_text(encoding="utf-8").lower()
            assert "powershell.exe" not in source and "-encodedcommand" not in source, module.name


class ComFailure(RuntimeError):
    def __init__(self, hresult, scode=None):
        super().__init__("PRIVATE exception path/token")
        self.hresult = hresult
        self.excepinfo = (None, None, "PRIVATE", None, None, scode)


class Definition:
    def __init__(self, xml=""):
        self.XmlText = xml

    @property
    def Principal(self):
        return SimpleNamespace(UserId=ET.fromstring(self.XmlText).findtext(f"{{{NS}}}Principals/{{{NS}}}Principal/{{{NS}}}UserId"))

    @property
    def RegistrationInfo(self):
        return SimpleNamespace(Description=ET.fromstring(self.XmlText).findtext(f"{{{NS}}}RegistrationInfo/{{{NS}}}Description"))

    @property
    def Actions(self):
        nodes = list(ET.fromstring(self.XmlText).find(f"{{{NS}}}Actions"))
        def item(index):
            node = nodes[index - 1]
            return SimpleNamespace(Arguments=node.findtext(f"{{{NS}}}Arguments"), Path=node.findtext(f"{{{NS}}}Command"))
        return SimpleNamespace(Count=len(nodes), Item=item)


class RegisteredTask:
    def __init__(self, xml):
        self.Definition = Definition(xml)
        self.LastTaskResult = 0
        self.running = False

    @property
    def Xml(self):
        return self.Definition.XmlText

    @property
    def Enabled(self):
        return ET.fromstring(self.Xml).findtext(f"{{{NS}}}Settings/{{{NS}}}Enabled") == "true"

    @Enabled.setter
    def Enabled(self, value):
        node = ET.fromstring(self.Xml)
        node.find(f"{{{NS}}}Settings/{{{NS}}}Enabled").text = str(value).lower()
        self.Definition.XmlText = ET.tostring(node, encoding="unicode")

    @property
    def State(self):
        return 4 if self.running else 3 if self.Enabled else 1

    def Run(self, ignored):
        assert self.Enabled
        self.running = True

    def Stop(self, ignored):
        self.running = False


class FakeCOM:
    def __init__(self):
        self.tasks = {}
        self.Connect = Mock()
        self.register_calls = 0
        self.GetFolder = Mock(return_value=self)

    def GetTask(self, name):
        if name not in self.tasks:
            raise ComFailure(0x80070002)
        return self.tasks[name]

    def NewTask(self, ignored):
        return Definition()

    def RegisterTask(self, name, xml, flags, sid, password, logon, sddl):
        assert flags == 6 and sid == SID and password is None and logon == 3
        assert not RegisteredTask(xml).Enabled
        self.register_calls += 1
        self.tasks[name] = RegisteredTask(xml)

    def DeleteTask(self, name, flags):
        del self.tasks[name]


def resolve(identity):
    if identity in (SID, "ASUS", "DOMAIN\\ASUS"):
        return SID
    if identity == "S-1-5-18":
        return identity
    raise ValueError("PRIVATE unresolvable name")


@pytest.fixture
def adapter(tmp_path):
    com = FakeCOM()

    def server(command, **options):
        data = json.loads(options["input"])
        assert "powershell" not in " ".join(command).lower() and "-EncodedCommand" not in command
        assert command[-1] == "auxdisp_codex_quota._scheduler_com_worker"
        result = worker.execute_operation(data, lambda: com, resolve)
        return SimpleNamespace(returncode=1 if "error" in result else 0, stdout=json.dumps(result), stderr="")

    runner = Mock(side_effect=server)
    cls = TaskScheduler
    backend = cls(SID, runner=runner)
    spec = TaskSpec(SID, tmp_path / "pythonw.exe", tmp_path / "config.toml", tmp_path / "codex-auth.exe", tmp_path)
    spec.python.write_bytes(b"not executed")
    spec.executable.write_bytes(b"not executed")
    return backend, com, spec, runner


@pytest.fixture
def controller(adapter, tmp_path, monkeypatch):
    backend, com, spec, _ = adapter

    class IPC:
        sid = SID

        @contextmanager
        def lock(self, *args, **kwargs):
            yield

        def running(self):
            return backend.name in com.tasks and com.tasks[backend.name].running

        def signal_stop(self):
            if backend.name in com.tasks:
                com.tasks[backend.name].running = False

    monkeypatch.setattr("auxdisp_codex_quota.service.resolve_executable", lambda requested: str(spec.executable))
    tick = [0.0]

    def sleep(seconds):
        tick[0] += seconds

    return ServiceController(backend, IPC(), AppPaths(tmp_path / "profile"),
                             clock=lambda: tick[0], sleep=sleep, start_timeout=1, stop_timeout=1,
                             spec_factory=lambda sid, config, executable, cwd:
                             TaskSpec(sid, spec.python, config, executable, cwd))


def test_lifecycle_contract_for_both_adapters(controller, adapter):
    backend, com, _, _ = adapter
    assert controller.execute("start")["process_running"]
    assert controller.execute("start")["process_running"]
    assert com.register_calls == 1
    assert controller.execute("status")["enabled"]
    assert not controller.execute("stop")["process_running"]
    assert controller.execute("restart")["process_running"]
    assert not controller.execute("uninstall-service")["registered"]
    assert backend.query() == {"registered": False}


@pytest.mark.parametrize("phase", ["register", "enable", "run"])
def test_lifecycle_failure_contract_for_both_adapters(controller, adapter, monkeypatch, phase):
    backend, _, _, _ = adapter
    original = backend.call

    def fail(operation, **values):
        if operation == phase:
            raise SchedulerError("ACCESS_DENIED", operation, "task_operation")
        return original(operation, **values)

    monkeypatch.setattr(backend, "call", fail)
    with pytest.raises(LifecycleError) as caught:
        controller.execute("start")
    assert caught.value.rollback == "restored" and caught.value.final_state["state"] == "missing"
    assert not controller.ipc.running()


def test_contract_register_disabled_query_enable_run_stop_delete(adapter):
    backend, com, spec, _ = adapter
    assert backend.query() == {"registered": False}
    backend.call("register", xml=spec.xml())
    assert not backend.query()["enabled"] and backend.query()["xml"]
    backend.call("enable")
    backend.call("run")
    assert backend.query()["state"] == 4
    backend.call("disable")
    assert backend.query()["state"] == 4 and not backend.query()["enabled"]
    backend.call("end")
    backend.call("delete")
    assert backend.query() == {"registered": False} and com.register_calls == 1


@pytest.mark.parametrize("identity", [SID, "ASUS", "DOMAIN\\ASUS"])
def test_contract_legacy_identity_and_arguments(adapter, identity):
    backend, com, spec, _ = adapter
    root = ET.fromstring(spec.xml())
    root.find(f"{{{NS}}}Principals/{{{NS}}}Principal/{{{NS}}}UserId").text = identity
    root.find(f"{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}Arguments").text = ARGUMENT_PREFIXES[0] + "--config test"
    com.tasks[backend.name] = RegisteredTask(ET.tostring(root, encoding="unicode"))
    assert backend.query()["registered"]
    backend.call("enable")
    assert backend.query()["enabled"]


@pytest.mark.parametrize("operation", ["query", "register", "enable", "disable", "run", "end", "delete"])
@pytest.mark.parametrize("bad,error", [
    ("different_user", "TASK_IDENTITY_MISMATCH"), ("unresolved", "TASK_IDENTITY_UNRESOLVED"),
    ("marker", "TASK_MARKER_MISMATCH"), ("actions", "TASK_ACTION_MISMATCH"),
])
def test_contract_unowned_collision_refused_for_every_operation(adapter, operation, bad, error):
    backend, com, spec, runner = adapter
    root = ET.fromstring(spec.xml())
    if bad in ("different_user", "unresolved"):
        root.find(f"{{{NS}}}Principals/{{{NS}}}Principal/{{{NS}}}UserId").text = (
            "S-1-5-18" if bad == "different_user" else "cannot-resolve")
    elif bad == "marker":
        root.find(f"{{{NS}}}RegistrationInfo/{{{NS}}}Description").text = "unrelated"
    else:
        actions = root.find(f"{{{NS}}}Actions")
        actions.append(deepcopy(list(actions)[0]))
    xml = ET.tostring(root, encoding="unicode")
    com.tasks[backend.name] = RegisteredTask(xml)
    with pytest.raises(SchedulerError, match=error):
        backend.call(operation, **({"xml": spec.xml()} if operation == "register" else {}))
    assert com.tasks[backend.name].Xml == xml and com.register_calls == 0
    runner.assert_called_once()


def test_contract_registration_rejects_initially_enabled_xml(adapter):
    backend, com, spec, _ = adapter
    root = ET.fromstring(spec.xml())
    root.find(f"{{{NS}}}Settings/{{{NS}}}Enabled").text = "true"
    with pytest.raises(SchedulerError, match="INVALID_TASK_SPEC"):
        backend.call("register", xml=ET.tostring(root, encoding="unicode"))
    assert not com.tasks and not com.register_calls


@pytest.mark.parametrize("code,scode,error", [
    (0x80070005, None, "ACCESS_DENIED"), (0x80020009, 0x80070005, "ACCESS_DENIED"),
    (0x800706BA, None, "COM_CALL_FAILED"),
])
def test_contract_hresult_classification_and_no_fallback(adapter, code, scode, error):
    backend, com, _, runner = adapter
    com.Connect.side_effect = ComFailure(code, scode)
    with pytest.raises(SchedulerError, match=error) as caught:
        backend.query()
    assert caught.value.stage == "connect" and "PRIVATE" not in str(caught.value)
    runner.assert_called_once()


def test_direct_timeout_starts_only_one_python_worker_and_reports_unknown():
    runner = Mock(side_effect=subprocess.TimeoutExpired(["PRIVATE command"], 20))
    with pytest.raises(SchedulerError, match="PROCESS_TIMEOUT") as caught:
        DirectComTaskScheduler(SID, runner).query()
    assert caught.value.stage == "com_worker_outcome_unknown"
    runner.assert_called_once()
    assert "powershell" not in " ".join(runner.call_args.args[0]).lower()


def test_direct_timeout_kills_and_reaps_its_python_child(monkeypatch):
    # The real subprocess timeout boundary is tested without COM or task access.
    children = []
    original = subprocess.Popen

    def track(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", track)

    def slow_worker(command, **options):
        return subprocess.run([sys.executable, "-c", "import time; time.sleep(30)"], **options)

    try:
        with pytest.raises(SchedulerError, match="PROCESS_TIMEOUT"):
            DirectComTaskScheduler(SID, runner=slow_worker, timeout=0.15).query()
        assert len(children) == 1 and children[0].poll() is not None
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


def test_direct_cancellation_is_unknown_and_never_falls_back():
    runner = Mock(side_effect=KeyboardInterrupt)
    with pytest.raises(SchedulerError, match="PROCESS_CANCELLED") as caught:
        DirectComTaskScheduler(SID, runner).query()
    assert caught.value.stage == "com_worker_outcome_unknown"
    runner.assert_called_once()


def test_worker_releases_com_apartment_on_failure(monkeypatch, capsys):
    api = SimpleNamespace(COINIT_APARTMENTTHREADED=2, CoInitializeEx=Mock(), CoUninitialize=Mock())
    com = FakeCOM()
    com.Connect.side_effect = ComFailure(0x80070005)
    monkeypatch.setitem(sys.modules, "pythoncom", api)
    monkeypatch.setitem(sys.modules, "win32security", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "win32com.client.dynamic", SimpleNamespace(Dispatch=lambda name: com))
    monkeypatch.setattr("auxdisp_codex_quota.win32.current_sid", lambda: SID)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(dict(operation="query", name="auxdisp-codex-quota-" + SID, sid=SID))))
    assert worker.main() == 1
    response = json.loads(capsys.readouterr().out)
    assert response["code"] == 0x80070005 and "PRIVATE" not in str(response)
    api.CoInitializeEx.assert_called_once_with(2)
    api.CoUninitialize.assert_called_once()


def test_worker_com_dependency_unavailable_is_explicit(monkeypatch, capsys):
    monkeypatch.setattr("auxdisp_codex_quota.win32.current_sid", lambda: SID)
    monkeypatch.setitem(sys.modules, "pythoncom", None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(dict(operation="query", name="auxdisp-codex-quota-" + SID, sid=SID))))
    assert worker.main() == 1
    assert json.loads(capsys.readouterr().out) == {"error": "COM_UNAVAILABLE"}


def test_worker_does_not_uninitialize_an_apartment_it_failed_to_initialize(monkeypatch, capsys):
    api = SimpleNamespace(COINIT_APARTMENTTHREADED=2,
                          CoInitializeEx=Mock(side_effect=ComFailure(0x800401F0)), CoUninitialize=Mock())
    monkeypatch.setitem(sys.modules, "pythoncom", api)
    monkeypatch.setitem(sys.modules, "win32security", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "win32com.client.dynamic", SimpleNamespace(Dispatch=Mock()))
    monkeypatch.setattr("auxdisp_codex_quota.win32.current_sid", lambda: SID)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(dict(operation="query", name="auxdisp-codex-quota-" + SID, sid=SID))))
    assert worker.main() == 1
    response = json.loads(capsys.readouterr().out)
    assert response["stage"] == "initialize_com" and response["code"] == 0x800401F0
    api.CoUninitialize.assert_not_called()
