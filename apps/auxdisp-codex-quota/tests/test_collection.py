import json
import sys
from types import SimpleNamespace
from threading import Event
import time

import pytest

from auxdisp_codex_quota.collector import CollectionWorker, Collector
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
