"""Opt-in WSL checks using synthetic processes, never accounts or USB.

Set AUXDISP_TEST_WSL to an installed distribution name to run these checks.
"""

import os
import json
import shutil
import subprocess
import time

import pytest

from auxdisp_codex_quota.collector import WSL_SUPERVISOR, CollectionWorker, Collector, WslLaunch
from auxdisp_codex_quota.model import DataError


pytestmark = pytest.mark.skipif(
    not os.environ.get("AUXDISP_TEST_WSL") or not shutil.which("wsl.exe"),
    reason="Set AUXDISP_TEST_WSL to opt into synthetic WSL process checks",
)


def command(script, duration="20"):
    return [shutil.which("wsl.exe"), "-d", os.environ["AUXDISP_TEST_WSL"], "-e",
            "/usr/bin/timeout", "-k", "1", duration, "/bin/bash", "-c", WSL_SUPERVISOR,
            "auxdisp-codex-quota", "/bin/bash", "-c", script]


@pytest.mark.parametrize(("script", "duration", "status"), [
    ("printf synthetic", "20", (0,)),
    ("sleep 60", "0.2", (124,)),
    ("trap '' TERM; printf ready; sleep 60", "0.2", (9, 137)),
])
def test_supervisor_preserves_success_and_timeout_status(script, duration, status):
    with subprocess.Popen(command(script, duration), stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            # communicate() would close the cancellation pipe immediately.
            assert process.wait(timeout=15) in status
            if status == (0,):
                assert process.stdout.read() == b"synthetic"
        finally:
            process.stdin.close()
            process.stdin = None
            process.communicate(timeout=10)


def test_pipe_eof_cancels_the_linux_process_and_its_descendant():
    script = 'sleep 60 & child=$!; printf "%s %s\\n" "$$" "$child"; wait "$child"'
    with subprocess.Popen(command(script), stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            pids = process.stdout.readline().decode().strip().split()
            assert len(pids) == 2 and all(pid.isdigit() for pid in pids)
        finally:
            process.stdin.close()
            process.stdin = None
            process.communicate(timeout=10)
        assert process.returncode in (9, 137)

    # Zombies have exited and can briefly await WSL init's reaper.
    probe = ('for pid in "$@"; do '
             'if read -r p comm state rest < "/proc/$pid/stat" 2>/dev/null; then '
             '[ "$state" = Z ] || exit 1; fi; done')
    result = subprocess.run(
        [shutil.which("wsl.exe"), "-d", os.environ["AUXDISP_TEST_WSL"], "-e",
         "/bin/bash", "-c", probe, "auxdisp-codex-quota", *pids],
        capture_output=True, timeout=10,
    )
    assert result.returncode == 0


def synthetic_collector(monkeypatch, script, duration="20"):
    launch = WslLaunch(os.environ["AUXDISP_TEST_WSL"], "/synthetic", "/usr/bin")
    collector = Collector(timeout=float(duration), wsl=launch)
    monkeypatch.setattr(collector, "_wsl_command", lambda: command(script, duration))
    return collector


def test_collector_reads_wsl_json_without_closing_the_control_pipe(monkeypatch, document):
    import shlex
    script = "printf '%s' " + shlex.quote(json.dumps(document))
    collector = synthetic_collector(monkeypatch, script)
    try:
        assert len(collector.collect()) == 3
    finally:
        collector.close()


@pytest.mark.parametrize("script", ["sleep 60", "trap '' TERM; sleep 60"])
def test_collector_reports_real_wsl_timeouts(monkeypatch, script):
    collector = synthetic_collector(monkeypatch, script, "0.2")
    try:
        with pytest.raises(DataError, match="^TIMEOUT$"):
            collector.collect()
    finally:
        collector.close()


def test_worker_cancel_during_wsl_start_does_not_stop_other_collection(monkeypatch):
    other = subprocess.Popen(command("printf ready; sleep 60"), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    collector = synthetic_collector(monkeypatch, "sleep 60")
    worker = CollectionWorker(collector)
    try:
        assert other.stdout.read(5) == b"ready"
        assert worker.request()
        deadline = time.monotonic() + 5
        while collector._process is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert collector._process is not None
        worker.close()
        assert not worker.thread.is_alive()
        assert worker.take().error == "COLLECTION_STOPPED"
        assert other.poll() is None
    finally:
        worker.close()
        other.stdin.close()
        other.stdin = None
        other.communicate(timeout=10)
