"""Idempotent lifecycle control; stop only this user's managed scheduled task."""

import json
from pathlib import Path
import time
import uuid

from .collector import resolve_executable
from .config import load_settings
from .model import DataError
from .paths import AppPaths, select_config
from .scheduler import TaskScheduler, TaskSpec
from .win32 import ServiceError, WindowsIPC


def read_state(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")
        for attempt in range(4):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.02)
    finally:
        temporary.unlink(missing_ok=True)


class ServiceController:
    def __init__(self, scheduler=None, ipc=None, paths=None, clock=None, sleep=None,
                 start_timeout=15, stop_timeout=30, spec_factory=None):
        self.ipc = ipc or WindowsIPC()
        self.scheduler = scheduler or TaskScheduler(self.ipc.sid)
        self.paths = paths or AppPaths.current()
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.start_timeout, self.stop_timeout = start_timeout, stop_timeout
        self.spec_factory = spec_factory or TaskSpec.installed

    def status(self):
        task = self.scheduler.query()
        running = self.ipc.running()
        state = read_state(self.paths.state)
        heartbeat = state.get("heartbeat")
        fresh = (running and isinstance(heartbeat, (int, float))
                 and 0 <= time.time() - heartbeat < 10 and state.get("phase") == "running")
        return {
            "task_name": self.scheduler.name,
            "registered": bool(task.get("registered")),
            "enabled": bool(task.get("enabled")),
            "scheduler_state": task.get("state"),
            "last_task_result": task.get("last_result"),
            "process_running": running,
            "health_fresh": bool(fresh),
            "usb_connected": state.get("usb_connected") if fresh else None,
            "last_success_at": state.get("last_success_at"),
            "phase": state.get("phase") if fresh else ("starting_or_unresponsive" if running else "stopped"),
            "mode": state.get("mode") if fresh else None,
            "last_stop": read_state(self.paths.state.parent / "last-stop.json"),
        }

    def _busy(self):
        return self.ipc.running() or self.scheduler.query().get("state") in (2, 4)

    def _stop(self):
        # Disable first, including pending crash recovery and future logon triggers.
        self.scheduler.call("disable")
        deadline = self.clock() + self.stop_timeout
        while self._busy() and self.clock() < deadline:
            self.ipc.signal_stop()
            self.sleep(0.2)
        forced = self._busy()
        if forced:
            if not self.scheduler.query().get("registered"):
                raise ServiceError("Foreground instance did not stop; no scheduled task exists to terminate")
            # The adapter verifies SID and task marker before this operation.
            self.scheduler.call("end")
            deadline = self.clock() + 5
            while self._busy() and self.clock() < deadline:
                self.sleep(0.2)
        if self._busy():
            raise ServiceError("The managed task has not exited; it remains disabled")
        state = read_state(self.paths.state)
        result = {"at": time.time(), "forced": forced, "cleanup_complete": state.get("cleanup_complete")}
        write_state(self.paths.state.parent / "last-stop.json", result)
        return result

    def _start(self, config=None):
        self.paths.root.mkdir(parents=True, exist_ok=True)
        selected = select_config(config, self.paths)
        if selected is None:
            try:
                with self.paths.config.open("x", encoding="utf-8") as file:
                    file.write("# auxdisp-codex-quota: defaults apply to omitted settings.\n")
            except FileExistsError:
                pass
            selected = self.paths.config
        settings = load_settings(selected)
        launch_path = self.paths.state.parent / "launch.json"
        launch = read_state(launch_path)
        try:
            executable = Path(resolve_executable(settings.executable)).resolve()
        except DataError:
            # An already-installed task must survive a later shell with a reduced PATH.
            if (launch.get("config") != str(selected) or launch.get("requested_executable") != settings.executable
                    or not Path(launch.get("executable", "")).is_file()):
                raise
            executable = Path(launch["executable"])
        spec = self.spec_factory(self.ipc.sid, selected, executable, self.paths.root)
        task = self.scheduler.query()
        changed = (task.get("description") != spec.description
                   or not Path(task.get("python", "")).is_file())
        if task.get("registered") and changed and self._busy():
            self._stop()
        if not task.get("registered") or changed:
            self.scheduler.call("register", xml=spec.xml())
        write_state(launch_path, {
            "config": str(selected), "requested_executable": settings.executable, "executable": str(executable),
        })
        self.scheduler.call("enable")
        if not self.ipc.running():
            # A queued/starting task will acquire the same mutex; do not run it twice.
            if self.scheduler.query().get("state") not in (2, 4):
                self.scheduler.call("run")
            deadline = self.clock() + self.start_timeout
            while not self.ipc.running() and self.clock() < deadline:
                self.sleep(0.2)
            if not self.ipc.running():
                raise ServiceError("Background startup was not confirmed; check logs/service.log and task status")
        return self.status()

    def execute(self, command, config=None):
        if command == "status":
            return self.status()
        with self.ipc.lock("control", timeout=5):
            if command == "start":
                return self._start(config)
            if command == "restart":
                stopped = self._stop()
                return dict(self._start(config), stop_result=stopped)
            if command == "stop":
                stopped = self._stop()
                return dict(self.status(), stop_result=stopped)
            if command == "uninstall-service":
                stopped = self._stop()
                self.scheduler.call("delete")
                return dict(self.status(), stop_result=stopped)
            raise ServiceError("Unknown lifecycle command")
