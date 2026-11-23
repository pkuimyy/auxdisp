import json
import subprocess
import sys
from types import SimpleNamespace
from threading import Event
import time

import pytest

from auxdisp_codex_quota.collector import (WSL_START_GRACE, CollectionWorker, Collector, WslLaunch,
                                           build_collector, resolve_wsl_launch)
from auxdisp_codex_quota.model import DataError


@pytest.mark.parametrize("nested", [False, True])
def test_windows_npm_launchers_resolve_the_native_binary(tmp_path, monkeypatch, nested):
    from auxdisp_codex_quota import collector as module
    launcher = tmp_path / "codex-auth.cmd"
    launcher.write_text("@echo off", encoding="utf-8")
    modules = tmp_path / "node_modules"
    root = modules / "@loongphy/codex-auth/node_modules" if nested else modules
    native = root / "@loongphy/codex-auth-win32-x64/bin/codex-auth.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"test binary path; never executed")
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(module.shutil, "which", lambda name: str(launcher))
    assert module.resolve_executable("codex-auth") == str(native)


def fake_command(tmp_path, monkeypatch, script):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "list").write_text(script, encoding="utf-8")
    return Collector(sys.executable, timeout=1)


def test_only_read_only_list_arguments_are_executed(tmp_path, monkeypatch, document, caplog):
    script = ("import sys\nassert sys.argv[1:]==['--api','--json']\n"
              "sys.stderr.write('CREDENTIAL_DO_NOT_LOG')\nprint(" + repr(json.dumps(document)) + ")")
    collector = fake_command(tmp_path, monkeypatch, script)
    assert len(collector.collect()) == 3
    assert "CREDENTIAL_DO_NOT_LOG" not in caplog.text
    collector.close()


@pytest.mark.parametrize("script,code", [
    ("print('bad json')", "INVALID_JSON"),
    ("import sys; print('private response'); sys.exit(1)", "COMMAND_EXIT_1"),
    ('print(\'{"schema_version":2}\')', "SCHEMA_UNSUPPORTED"),
])
def test_process_and_protocol_failures_use_safe_codes(tmp_path, monkeypatch, script, code):
    collector = fake_command(tmp_path, monkeypatch, script)
    with pytest.raises(DataError, match=code):
        collector.collect()
    assert collector._process is None


def test_timeout_terminates_child_process(tmp_path, monkeypatch):
    collector = fake_command(tmp_path, monkeypatch, "import time; time.sleep(30)")
    collector.timeout = 0.1
    started = time.monotonic()
    with pytest.raises(DataError, match="TIMEOUT"):
        collector.collect()
    assert time.monotonic() - started < 6
    assert collector._process is None


def test_missing_executable_is_recoverable():
    with pytest.raises(DataError, match="COMMAND_NOT_FOUND"):
        Collector("auxdisp-no-such-command-123456").collect()


def test_native_mode_does_not_remap_exit_status_124(tmp_path, monkeypatch):
    collector = fake_command(tmp_path, monkeypatch, "import sys; sys.exit(124)")
    with pytest.raises(DataError, match="COMMAND_EXIT_124"):
        collector.collect()


WSL_EXE = "C:\\Windows\\System32\\wsl.exe"
WSL_RESOLVE_SCRIPT = ('p=$(command -v codex-auth) && printf "codex:%s\\n" "$p"; '
                      'n=$(command -v node) && printf "node:%s\\n" "$n"')


def completed(returncode=0, stdout=b"", stderr=b""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def use_wsl_exe(monkeypatch, present=True):
    monkeypatch.setattr("auxdisp_codex_quota.collector.shutil.which",
                        lambda name: WSL_EXE if present else None)


class FakeRun:
    """Replays queued subprocess.run responses and records every command."""

    def __init__(self, monkeypatch, responses):
        self.responses, self.calls = list(responses), []
        monkeypatch.setattr("auxdisp_codex_quota.collector.subprocess.run", self)

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_wsl_resolution_requires_wsl_exe(monkeypatch):
    use_wsl_exe(monkeypatch, present=False)
    with pytest.raises(DataError, match="WSL_NOT_INSTALLED"):
        resolve_wsl_launch("Ubuntu-24.04")


def test_wsl_resolution_uses_the_distribution_login_shell(monkeypatch):
    use_wsl_exe(monkeypatch)
    run = FakeRun(monkeypatch, [completed(stdout=(
        b"codex:/home/u/.nvm/versions/node/v24.14.0/bin/codex-auth\r\n"
        b"node:/home/u/.nvm/versions/node/v24.14.0/bin/node\r\n"))])
    launch = resolve_wsl_launch(" Ubuntu-24.04 ")
    assert launch == WslLaunch("Ubuntu-24.04", "/home/u/.nvm/versions/node/v24.14.0/bin/codex-auth",
                               "/home/u/.nvm/versions/node/v24.14.0/bin")
    assert run.calls[0][1:6] == ["-d", "Ubuntu-24.04", "-e", "bash", "-lic"]
    assert run.calls[0][6] == WSL_RESOLVE_SCRIPT


def test_wsl_resolution_distinguishes_a_missing_distribution(monkeypatch):
    use_wsl_exe(monkeypatch)
    run = FakeRun(monkeypatch, [completed(returncode=1),
                                completed(stdout="Ubuntu-24.04\r\n".encode("utf-16"))])
    with pytest.raises(DataError, match="WSL_DISTRO_MISSING"):
        resolve_wsl_launch("Ubuntu-99.99")
    assert run.calls[1][1:] == ["--list", "--quiet"]


def test_wsl_resolution_reports_unresolved_commands_in_existing_distribution(monkeypatch):
    use_wsl_exe(monkeypatch)
    FakeRun(monkeypatch, [completed(stdout=b"node:/usr/bin/node\r\n"),
                          completed(stdout="Ubuntu-24.04\r\n".encode("utf-16-le"))])
    with pytest.raises(DataError, match="WSL_RESOLVE_FAILED"):
        resolve_wsl_launch("Ubuntu-24.04")


def test_wsl_resolution_reports_startup_hangs(monkeypatch):
    use_wsl_exe(monkeypatch)
    FakeRun(monkeypatch, [subprocess.TimeoutExpired("wsl", 30)])
    with pytest.raises(DataError, match="WSL_RESOLVE_FAILED"):
        resolve_wsl_launch("Ubuntu-24.04")


def test_wsl_launch_requires_a_distribution_and_absolute_linux_paths():
    for arguments in (("", "/home/u/bin/codex-auth", "/home/u/bin"),
                      ("Ubuntu-24.04", "codex-auth", "/home/u/bin"),
                      ("Ubuntu-24.04", "/home/u/bin/codex-auth", "home/u/bin")):
        with pytest.raises(ValueError):
            WslLaunch(*arguments)


class FakePopen:
    """Records the launch command; class attributes drive the communication result."""

    instances = []
    result = (b"", b"", 0)
    expire_at = None
    terminated = []

    def __init__(self, command, **kwargs):
        self.command, self.kwargs = command, kwargs
        self.timeouts = []
        FakePopen.instances.append(self)

    def communicate(self, timeout=None):
        self.timeouts.append(timeout)
        if timeout is not None and FakePopen.expire_at is not None and timeout >= FakePopen.expire_at:
            raise subprocess.TimeoutExpired("wsl", timeout)
        return FakePopen.result[0], FakePopen.result[1]

    @property
    def returncode(self):
        return FakePopen.result[2]


@pytest.fixture
def fake_wsl_process(monkeypatch):
    FakePopen.instances, FakePopen.result, FakePopen.expire_at, FakePopen.terminated = [], (b"", b"", 0), None, []
    monkeypatch.setattr("auxdisp_codex_quota.collector.subprocess.Popen", FakePopen)
    monkeypatch.setattr("auxdisp_codex_quota.collector.terminate_tree", FakePopen.terminated.append)
    return FakePopen


def test_wsl_collection_builds_read_only_command_and_forwards_proxy(monkeypatch, document, fake_wsl_process):
    use_wsl_exe(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    fake_wsl_process.result = (json.dumps(document).encode(), b"", 0)
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    collector = Collector(launch.executable, timeout=20, wsl=launch)
    assert len(collector.collect()) == 3
    command = fake_wsl_process.instances[0].command
    assert command[:8] == [WSL_EXE, "-d", "Ubuntu-24.04", "-e", "/usr/bin/timeout", "-k", "5", "20"]
    assert command[8] == "env"
    assert "PATH=/home/u/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" in command
    assert "HTTP_PROXY=http://127.0.0.1:7890" in command
    assert "NODE_USE_ENV_PROXY=1" in command
    assert not any(entry.startswith(("HTTPS_PROXY=", "NO_PROXY=")) for entry in command)
    assert command[-4:] == ["/home/u/bin/codex-auth", "list", "--api", "--json"]


def test_wsl_collection_reports_uninstalled_wsl(monkeypatch, fake_wsl_process):
    use_wsl_exe(monkeypatch, present=False)
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    with pytest.raises(DataError, match="WSL_NOT_INSTALLED"):
        Collector(launch.executable, timeout=20, wsl=launch).collect()


def test_wsl_collection_budget_includes_startup_grace(monkeypatch, document, fake_wsl_process):
    use_wsl_exe(monkeypatch)
    fake_wsl_process.result = (json.dumps(document).encode(), b"", 0)
    fake_wsl_process.expire_at = 7 + WSL_START_GRACE + 0.5
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    assert len(Collector(launch.executable, timeout=7, wsl=launch).collect()) == 3
    assert fake_wsl_process.instances[0].timeouts == [7 + WSL_START_GRACE]


def test_wsl_collection_reports_grace_expiry_as_timeout(monkeypatch, fake_wsl_process):
    use_wsl_exe(monkeypatch)
    fake_wsl_process.expire_at = 10
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    with pytest.raises(DataError, match="TIMEOUT"):
        Collector(launch.executable, timeout=7, wsl=launch).collect()
    assert fake_wsl_process.instances[0].timeouts == [7 + WSL_START_GRACE, None]
    assert fake_wsl_process.terminated == [fake_wsl_process.instances[0]]


def test_wsl_linux_timeout_exit_status_maps_to_timeout(monkeypatch, fake_wsl_process):
    use_wsl_exe(monkeypatch)
    fake_wsl_process.result = (b"", b"", 124)
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    with pytest.raises(DataError, match="TIMEOUT"):
        Collector(launch.executable, timeout=20, wsl=launch).collect()
    assert fake_wsl_process.terminated == []


def test_wsl_other_failures_keep_command_exit_codes(monkeypatch, fake_wsl_process):
    use_wsl_exe(monkeypatch)
    fake_wsl_process.result = (b"", b"", 2)
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    with pytest.raises(DataError, match="COMMAND_EXIT_2"):
        Collector(launch.executable, timeout=20, wsl=launch).collect()


def test_build_collector_selects_the_configured_source(monkeypatch):
    launch = WslLaunch("Ubuntu-24.04", "/home/u/bin/codex-auth", "/home/u/bin")
    monkeypatch.setattr("auxdisp_codex_quota.collector.resolve_wsl_launch",
                        lambda distribution, name: launch)
    assert build_collector("codex-auth", 20, "Ubuntu-24.04").wsl == launch
    plain = build_collector("codex-auth", 20)
    assert plain.wsl is None and plain.executable == "codex-auth"


def test_collection_worker_never_overlaps_or_grows_a_result_queue():
    entered, release = Event(), Event()

    class Blocked:
        calls = 0

        def collect(self):
            self.calls += 1
            entered.set()
            release.wait(3)
            return ()

        def close(self):
            release.set()

    collector = Blocked()
    worker = CollectionWorker(collector)
    try:
        assert worker.request()
        assert entered.wait(1)
        assert not worker.request()
        worker.close()
        assert not worker.thread.is_alive()
        assert worker.results.qsize() == 1
        assert not worker.request()
        assert worker.take().accounts == ()
        assert collector.calls == 1
    finally:
        release.set()
        worker.close()
