"""Explicitly authorized Windows task acceptance, never an automatic check.

Creates uniquely named current-user tasks, uses synthetic accounts, and may
write the connected display and normal diagnostic state/logs. Never edits the
normal task. Stops on policy/access denial without switching transports.
"""

from dataclasses import replace
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from auxdisp_codex_quota.direct_com import DirectComTaskScheduler
from auxdisp_codex_quota.paths import AppPaths
from auxdisp_codex_quota.service import LifecycleError, ServiceController, read_state
from auxdisp_codex_quota.task_spec import TaskSpec
from auxdisp_codex_quota.win32 import ServiceError, WindowsIPC


class LegacySpec(TaskSpec):
    @property
    def arguments(self):
        return super().arguments.replace("-E -P -m ", "-I -m ", 1)


class HelpSpec(TaskSpec):
    @property
    def arguments(self):
        return super().arguments + " --help"


def scheduler(name=None):
    value = DirectComTaskScheduler()
    if name:
        if not name.startswith(value.name + "-local-acceptance-"):
            raise ValueError("Only this run's task namespace is allowed")
        value.name = name
    return value


def controller(name, root, factory=None, timeout=15):
    return ServiceController(scheduler(name), WindowsIPC(), AppPaths(root),
                             spec_factory=factory, start_timeout=timeout, stop_timeout=8)


def short_status(status):
    # Controller metadata is isolated under the test profile, while the actual
    # scheduled host uses normal diagnostic state. Report those scopes honestly.
    result = {key: status[key] for key in ("registered", "enabled", "process_running") if key in status}
    health = read_state(AppPaths.current().state)
    result["host_phase"] = health.get("phase")
    result["host_health_fresh"] = (type(health.get("heartbeat")) in (int, float)
                                   and 0 <= time.time() - health["heartbeat"] < 10)
    return result


def child_control(name, root, operation):
    result = subprocess.run(
        [sys.executable, "-E", "-P", str(Path(__file__).resolve()), "--child-control", operation,
         "--task-name", name, "--root", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=100,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    payload = json.loads(result.stdout)
    if result.returncode:
        raise ServiceError(payload.get("error", "CONTROL_FAILED"))
    return payload


def wait_instance(expected, timeout=15):
    deadline = time.monotonic() + timeout
    while WindowsIPC().running() != expected and time.monotonic() < deadline:
        time.sleep(0.2)
    if WindowsIPC().running() != expected:
        raise ServiceError("INSTANCE_CONFIRMATION_FAILED")


def run(root):
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "native-acceptance.json"
    original = scheduler()
    initial = original.query()
    if WindowsIPC().running() or initial.get("state") in (2, 4):
        raise ServiceError("EXISTING_INSTANCE_RUNNING: no test tasks created")
    run_id = uuid.uuid4().hex
    prefix = original.name + "-local-acceptance-" + run_id
    names = [prefix, prefix + "-missing", prefix + "-timeout"]
    report = {"run_id": run_id, "status": "RUNNING", "cases": [], "operations_blocked": False}

    def record(case, **values):
        item = dict(case=case, **values)
        report["cases"].append(item)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(item), flush=True)

    profile = root / "profile"
    profile.mkdir(exist_ok=True)
    config = profile / "config.toml"
    config.write_text("[collector]\nexecutable = '" + sys.executable + "'\nrefresh_seconds = 3\n"
                      "[rotation]\nseconds = 2\n[display]\nbrightness = 30\n", encoding="utf-8")
    (profile / "list").write_text(
        "from importlib.resources import files\n"
        "print(files('auxdisp_codex_quota').joinpath('data/demo.json').read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )
    try:
        for name in names:
            if scheduler(name).query().get("registered"):
                raise ServiceError("TEST_NAMESPACE_COLLISION")
        record("first_start", **child_control(prefix, profile, "start"))
        time.sleep(2)
        health_before = read_state(AppPaths.current().state)
        record("controller_exited_background_survives", running=WindowsIPC().running(),
               health_running=health_before.get("phase") == "running")
        assert WindowsIPC().running() and health_before.get("phase") == "running"
        record("repeat_start", **child_control(prefix, profile, "start"))
        health_after = read_state(AppPaths.current().state)
        assert health_after.get("instance") == health_before.get("instance")
        record("single_instance", unchanged=True)
        record("status", **child_control(prefix, profile, "status"))
        record("stop", **child_control(prefix, profile, "stop"))
        assert not WindowsIPC().running() and not scheduler(prefix).query()["enabled"]
        record("restart", **child_control(prefix, profile, "restart"))
        child_control(prefix, profile, "stop")
        legacy = LegacySpec.installed(WindowsIPC().sid, config, Path(sys.executable), profile)
        scheduler(prefix).call("register", xml=legacy.xml())
        scheduler(prefix).call("enable")
        scheduler(prefix).call("run")
        wait_instance(True)
        record("legacy_instance_started", running=True)
        child_control(prefix, profile, "restart")
        migrated = scheduler(prefix).query()
        assert migrated["description"] != legacy.description and "-E -P -m " in migrated["xml"]
        record("legacy_migration", migrated=True, running=WindowsIPC().running())

        def missing(sid, selected, executable, cwd):
            return replace(TaskSpec.installed(sid, selected, executable, cwd), python=profile / "missing-pythonw.exe")

        # Keep this owned task running, then force an actual file-not-found Run
        # failure during replacement; the old running definition must return.
        before = scheduler(prefix).query()
        try:
            controller(prefix, profile, missing, timeout=5).execute("start", config)
            raise AssertionError("Expected native Run failure")
        except LifecycleError as exc:
            record("failed_replacement_observed", rollback=exc.rollback, state=exc.final_state)
            if "ACCESS_DENIED" in str(exc) or "PROCESS_START_FAILED" in str(exc):
                raise
            assert exc.rollback == "restored" and exc.final_state["process_running"]
            assert scheduler(prefix).query()["description"] == before["description"]
            record("failed_replacement_restores_original", rollback=exc.rollback, state=exc.final_state)
        record("uninstall_service", **child_control(prefix, profile, "uninstall-service"))
        assert not WindowsIPC().running()

        try:
            controller(names[1], profile, missing, timeout=5).execute("start", config)
            raise AssertionError("Expected native Run failure")
        except LifecycleError as exc:
            if "ACCESS_DENIED" in str(exc) or "PROCESS_START_FAILED" in str(exc):
                raise
            assert exc.rollback == "restored" and not scheduler(names[1]).query()["registered"]
            record("new_run_failure_cleaned", rollback=exc.rollback, state=exc.final_state)

        def help_only(sid, selected, executable, cwd):
            return HelpSpec.installed(sid, selected, executable, cwd)

        try:
            controller(names[2], profile, help_only, timeout=2).execute("start", config)
            raise AssertionError("Expected startup confirmation timeout")
        except LifecycleError as exc:
            if "ACCESS_DENIED" in str(exc) or "PROCESS_START_FAILED" in str(exc):
                raise
            assert exc.rollback == "restored" and not scheduler(names[2]).query()["registered"]
            record("startup_confirmation_timeout_cleaned", rollback=exc.rollback, state=exc.final_state)
        report["status"] = "PASSED"
    except Exception as exc:
        text = str(exc) if isinstance(exc, ServiceError) else type(exc).__name__
        report["error"] = text
        # Access denial does not identify antivirus versus ACL/process policy.
        # Stop further calls without asserting an unproven security rule.
        report["operations_blocked"] = any(code in text for code in ("ACCESS_DENIED", "PROCESS_START_FAILED", "PROCESS_CANCELLED"))
        report["status"] = "BLOCKED" if report["operations_blocked"] else "FAILED"
        raise
    finally:
        if not report["operations_blocked"]:
            try:
                for name in names:
                    if scheduler(name).query().get("registered"):
                        controller(name, profile).execute("uninstall-service")
                report["test_tasks_removed"] = all(not scheduler(name).query().get("registered") for name in names)
                report["instance_stopped"] = not WindowsIPC().running()
                report["original_task_unchanged"] = original.query() == initial
                if not all(report[key] for key in ("test_tasks_removed", "instance_stopped", "original_task_unchanged")):
                    report["status"] = "CLEANUP_FAILED"
                    report["cleanup_error"] = "POSTCHECK_FAILED"
            except Exception as cleanup:
                report["cleanup_error"] = str(cleanup) if isinstance(cleanup, ServiceError) else type(cleanup).__name__
                report["status"] = "CLEANUP_FAILED"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-task-writes", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--child-control", choices=("start", "status", "stop", "restart", "uninstall-service"))
    parser.add_argument("--task-name")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Windows is required")
    if args.child_control:
        try:
            result = controller(args.task_name, args.root).execute(args.child_control, args.root / "config.toml")
            print(json.dumps(short_status(result)))
            return 0
        except ServiceError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1
    if not args.allow_task_writes:
        parser.error("Explicit local task-write authorization is required")
    try:
        result = run(args.root.resolve())
        print(json.dumps({key: value for key, value in result.items() if key != "cases"}))
        return 0 if result["status"] == "PASSED" else 1
    except Exception as exc:
        print(json.dumps({"error": str(exc) if isinstance(exc, ServiceError) else type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
