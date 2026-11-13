"""Validate a real installed CLI against its normal per-user task and profile.

Explicit authorization required. Refuses an existing task/instance; uses only
synthetic data, removes the task it creates, and restores prior state files.
Never changes the default config or switches backend after an access failure.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from auxdisp_codex_quota.scheduler import TaskScheduler
from auxdisp_codex_quota.paths import AppPaths
from auxdisp_codex_quota.service import read_state
from auxdisp_codex_quota.win32 import ServiceError, WindowsIPC


def validate(cli, python, root, label):
    root.mkdir(parents=True, exist_ok=True)
    report = {"installation": label, "status": "RUNNING", "cases": []}
    report_file = root / "cli-acceptance.json"
    scheduler, ipc, paths = TaskScheduler(), WindowsIPC(), AppPaths.current()
    if scheduler.query().get("registered") or ipc.running():
        raise ServiceError("EXISTING_TASK_OR_INSTANCE: no formal task overwritten")
    profile = paths.root
    profile.mkdir(parents=True, exist_ok=True)
    list_file = profile / "list"
    if list_file.exists():
        raise ServiceError("EXISTING_COLLECTOR_TEST_FILE: refusing to overwrite")
    config_before = paths.config.read_bytes() if paths.config.exists() else None
    state_files = [paths.state, paths.state.parent / "launch.json", paths.state.parent / "last-stop.json"]
    before = {p: p.read_bytes() if p.exists() else None for p in state_files}
    code = ("from importlib.resources import files\n"
            "print(files('auxdisp_codex_quota').joinpath('data/demo.json').read_text(encoding='utf-8'))\n")
    with list_file.open("x", encoding="utf-8") as file:
        file.write(code)
    owned_hash = hashlib.sha256(list_file.read_bytes()).hexdigest()
    config = root / "synthetic.toml"
    config.write_text("[collector]\nexecutable = " + json.dumps(str(python)) + "\nrefresh_seconds = 3\n"
                      "[rotation]\nseconds = 2\n[display]\nbrightness = 30\n", encoding="utf-8")
    blocked = False
    touched = False

    def save():
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def call(operation):
        nonlocal blocked, touched
        args = [str(cli), operation]
        if operation in ("start", "restart"):
            args.extend(["--config", str(config)])
        if operation == "status":
            args.append("--json")
        else:
            touched = True
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=100, creationflags=subprocess.CREATE_NO_WINDOW, cwd=root)
        if result.returncode:
            blocked = any(code in result.stderr for code in ("ACCESS_DENIED", "PROCESS_START_FAILED", "PROCESS_CANCELLED"))
            # No raw stderr/paths enter the report.
            raise ServiceError(f"CLI_{operation.upper()}_FAILED exit_code={result.returncode} blocked={blocked}")
        return json.loads(result.stdout) if operation == "status" else call("status")

    def record(operation, result):
        safe = {key: result.get(key) for key in ("registered", "enabled", "process_running", "health_fresh", "phase")}
        report["cases"].append(dict(operation=operation, **safe))
        save()
        print(json.dumps(dict(installation=label, operation=operation, **safe)), flush=True)

    try:
        record("start", call("start"))
        deadline = time.monotonic() + 10
        status = call("status")
        while not status["health_fresh"] and time.monotonic() < deadline:
            time.sleep(0.3)
            status = call("status")
        assert status["process_running"] and status["health_fresh"] and status["phase"] == "running"
        host = read_state(paths.state)
        record("status_after_cli_exit", status)
        record("repeated_start", call("start"))
        assert read_state(paths.state).get("instance") == host.get("instance")
        report["single_instance"] = True
        record("stop", call("stop"))
        assert not ipc.running() and not scheduler.query()["enabled"]
        record("restart", call("restart"))
        assert ipc.running()
        record("uninstall-service", call("uninstall-service"))
        assert not scheduler.query().get("registered") and not ipc.running()
        report["status"] = "PASSED"
    except Exception as exc:
        report["status"] = "BLOCKED" if blocked else "FAILED"
        report["error"] = str(exc) if isinstance(exc, ServiceError) else type(exc).__name__
        raise
    finally:
        if not blocked:
            try:
                if touched and scheduler.query().get("registered"):
                    call("uninstall-service")
                report["test_task_removed"] = not scheduler.query().get("registered")
                report["instance_stopped"] = not ipc.running()
                if not report["test_task_removed"] or not report["instance_stopped"]:
                    raise ServiceError("CLEANUP_UNCONFIRMED")
                if hashlib.sha256(list_file.read_bytes()).hexdigest() != owned_hash:
                    raise ServiceError("TEST_FILE_CHANGED_EXTERNALLY")
                list_file.unlink()
                for file, data in before.items():
                    if data is None:
                        file.unlink(missing_ok=True)
                    else:
                        file.parent.mkdir(parents=True, exist_ok=True)
                        file.write_bytes(data)
                config_after = paths.config.read_bytes() if paths.config.exists() else None
                report["default_config_unchanged"] = config_after == config_before
                report["diagnostic_state_restored"] = all(
                    (p.read_bytes() if p.exists() else None) == data for p, data in before.items())
                if not report["default_config_unchanged"] or not report["diagnostic_state_restored"]:
                    raise ServiceError("PROFILE_RESTORE_UNCONFIRMED")
            except Exception as exc:
                report["status"] = "CLEANUP_FAILED"
                report["cleanup_error"] = str(exc) if isinstance(exc, ServiceError) else type(exc).__name__
        else:
            report["cleanup"] = "not_retried_after_block; state_unknown"
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-default-task-test", action="store_true")
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not args.allow_default_task_test:
        parser.error("Explicit task-write authorization required")
    try:
        result = validate(args.cli.resolve(), args.python.resolve(), args.root.resolve(), args.label)
        print(json.dumps({key: value for key, value in result.items() if key != "cases"}))
        return 0 if result["status"] == "PASSED" else 1
    except Exception as exc:
        print(json.dumps({"error": str(exc) if isinstance(exc, ServiceError) else type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
