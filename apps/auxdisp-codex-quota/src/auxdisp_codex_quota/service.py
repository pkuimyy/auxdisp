"""Idempotent lifecycle control; stop only this user's managed scheduled task."""

import json
from dataclasses import dataclass
from pathlib import Path
import time
import uuid
from xml.etree import ElementTree as ET

from .collector import resolve_executable
from .config import load_settings
from .model import DataError
from .paths import AppPaths, select_config
from .task_spec import NS, TaskSpec
from .task_adapter import SchedulerError, TaskSchedulerAdapter, default_scheduler
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


@dataclass
class Transition:
    before: dict
    was_running: bool
    identity_sid: str
    launch_before: bytes | None
    expected_description: str | None = None
    expected_xml: str | None = None
    dirty: bool = False
    ran: bool = False
    stopped: bool = False


class LifecycleError(ServiceError):
    def __init__(self, command, cause, final_state, rollback, cleanup_error=None):
        self.command, self.final_state, self.rollback = command, final_state, rollback
        self.cleanup_error = cleanup_error
        self.before_state, self.identity_sid, self.identity_verified = None, None, False
        # Backend/DataError messages are deliberately safe. Arbitrary OS/config
        # exceptions can contain private paths or file contents and are not echoed.
        detail = str(cause) if isinstance(cause, (ServiceError, DataError)) else type(cause).__name__
        super().__init__(f"LIFECYCLE_{command.upper()}_FAILED: {detail}; rollback={rollback}; "
                         f"final_state={json.dumps(final_state, sort_keys=True)}"
                         f"{('; cleanup=' + cleanup_error) if cleanup_error else ''}")


def state_summary(task=None, running=None):
    if task is None:
        return {"state": "unknown", "registered": None, "enabled": None, "process_running": running}
    present = bool(task.get("registered"))
    enabled = bool(task.get("enabled")) if present else False
    state = ("running" if running else "starting" if task.get("state") in (2, 4) else
             "missing" if not present else "enabled" if enabled else "disabled")
    return {"state": state, "registered": present, "enabled": enabled, "process_running": running,
            "scheduler_state": task.get("state")}


def disabled_xml(xml):
    root = ET.fromstring(xml)
    # Task Scheduler omits settings whose values equal schema defaults. In
    # particular, an enabled task's canonical XML may have no Enabled node.
    settings = root.find(f"{{{NS}}}Settings")
    if settings is None:
        settings = ET.Element(f"{{{NS}}}Settings")
        actions = root.find(f"{{{NS}}}Actions")
        root.insert(list(root).index(actions) if actions is not None else len(root), settings)
    enabled = settings.find(f"{{{NS}}}Enabled")
    if enabled is None:
        enabled = ET.SubElement(settings, f"{{{NS}}}Enabled")
    enabled.text = "false"
    return ET.tostring(root, encoding="unicode")


def definition_identity(xml):
    """Compare management/launch identity without COM's Enabled serialization.

    Principal aliases are already normalized and checked by the adapter; do not
    reintroduce string comparisons between names and SIDs here.
    """
    if not xml:
        raise ServiceError("TASK_SNAPSHOT_INCOMPLETE: task launch identity is unavailable")
    root = ET.fromstring(xml)
    return tuple(root.findtext(path) for path in (
        f"{{{NS}}}RegistrationInfo/{{{NS}}}Description",
        f"{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}Command",
        f"{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}Arguments",
        f"{{{NS}}}Actions/{{{NS}}}Exec/{{{NS}}}WorkingDirectory",
    ))


class ServiceController:
    def __init__(self, scheduler: TaskSchedulerAdapter | None = None, ipc=None, paths=None, clock=None, sleep=None,
                 start_timeout=15, stop_timeout=30, spec_factory=None):
        self.ipc = ipc or WindowsIPC()
        self.scheduler = scheduler or default_scheduler(self.ipc.sid)
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

    def _call(self, transition, operation, **values):
        if operation == "register":
            root = ET.fromstring(values["xml"])
            transition.expected_description = root.findtext(f"{{{NS}}}RegistrationInfo/{{{NS}}}Description")
            transition.expected_xml = values["xml"]
        transition.dirty = True  # Even an exception can follow a committed COM write.
        # Enabling can itself release a queued/logon trigger. Treat it as a
        # possible activation unless the original healthy instance is protected.
        if operation == "run" or (operation == "enable" and (not transition.was_running or transition.stopped)):
            transition.ran = True
        return self.scheduler.call(operation, **values)

    def _stop(self, transition):
        was_busy = self._busy()
        previous_state = read_state(self.paths.state)
        previous_instance = previous_state.get("instance")
        # Disable first, including pending crash recovery and future logon triggers.
        if self.scheduler.query().get("registered"):
            self._call(transition, "disable")
        elif self.ipc.running():
            transition.dirty = True
        deadline = self.clock() + self.stop_timeout
        while self._busy() and self.clock() < deadline:
            self.ipc.signal_stop()
            self.sleep(0.2)
        forced = self._busy()
        if forced:
            if not self.scheduler.query().get("registered"):
                raise ServiceError("Foreground instance did not stop; no scheduled task exists to terminate")
            # The adapter verifies SID and task marker before this operation.
            self._call(transition, "end")
            deadline = self.clock() + 5
            while self._busy() and self.clock() < deadline:
                self.sleep(0.2)
        if self._busy():
            raise ServiceError("The managed task has not exited; it remains disabled")
        transition.stopped = True
        state = read_state(self.paths.state)
        confirmed = (was_busy and not forced and previous_instance is not None
                     and previous_state.get("phase") == "running"
                     and previous_instance == state.get("instance") and state.get("phase") == "stopped")
        result = {
            "at": time.time(), "forced": forced,
            "cleanup_complete": state.get("cleanup_complete") if confirmed else None,
            "screen_off": state.get("screen_off", "unknown") if confirmed else (
                "unknown" if was_busy else "not_attempted"
            ),
        }
        write_state(self.paths.state.parent / "last-stop.json", result)
        return result

    def _start(self, transition, config=None):
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
        if task.get("registered") and changed:
            if not transition.before.get("xml"):
                raise ServiceError("TASK_SNAPSHOT_INCOMPLETE: task cannot be safely restored")
            if self._busy():
                self._stop(transition)
        if not task.get("registered") or changed:
            self._call(transition, "register", xml=spec.xml())
            # A new or replaced task must be owned, disabled and match the spec
            # before it is ever enabled. Registration itself is not activation.
            verified = self.scheduler.query()
            if (not verified.get("registered") or verified.get("enabled")
                    or verified.get("description") != spec.description
                    or definition_identity(verified.get("xml")) != definition_identity(spec.xml())):
                raise ServiceError("TASK_REGISTRATION_UNCONFIRMED: disabled registration did not match spec")
        if not task.get("enabled") or changed:
            self._call(transition, "enable")
        if not self.ipc.running():
            # A queued/starting task will acquire the same mutex; do not run it twice.
            if self.scheduler.query().get("state") not in (2, 4):
                self._call(transition, "run")
            deadline = self.clock() + self.start_timeout
            while not self.ipc.running() and self.clock() < deadline:
                self.sleep(0.2)
            if not self.ipc.running():
                raise ServiceError("Background startup was not confirmed; check logs/service.log and task status")
        write_state(launch_path, {
            "config": str(selected), "requested_executable": settings.executable, "executable": str(executable),
        })
        return self.status()

    def _observe(self, failure=None):
        if isinstance(failure, SchedulerError) and failure.kind in ("PROCESS_START_FAILED", "PROCESS_TIMEOUT", "PROCESS_CANCELLED"):
            return state_summary()
        try:
            return state_summary(self.scheduler.query(), self.ipc.running())
        except Exception:
            return state_summary()

    def _rollback(self, transition):
        current = self.scheduler.query()  # Ownership checked again before cleanup.
        allowed = {transition.before.get("description"), transition.expected_description}
        if current.get("registered") and current.get("description") not in allowed:
            raise ServiceError("ROLLBACK_IDENTITY_CHANGED: no cleanup performed")
        if current.get("registered"):
            identities = {definition_identity(xml) for xml in
                          (transition.before.get("xml"), transition.expected_xml) if xml}
            if definition_identity(current.get("xml")) not in identities:
                raise ServiceError("ROLLBACK_IDENTITY_CHANGED: task launch identity changed; no cleanup performed")
        if transition.ran:
            if not current.get("registered") and self.ipc.running():
                raise ServiceError("ROLLBACK_INSTANCE_UNKNOWN: no task owns the observed instance")
            # Only this transition's run attempt may be stopped during rollback.
            # A healthy instance that predated an early failure is never stopped.
            if current.get("registered"):
                self._stop(transition)
                current = self.scheduler.query()
        before = transition.before
        if not before.get("registered"):
            if current.get("registered"):
                self._call(transition, "disable")
                self._call(transition, "delete")
        else:
            same_definition = (current.get("registered") and current.get("description") == before.get("description")
                               and (current.get("xml") == before.get("xml") or
                                    (current.get("xml") and before.get("xml") and
                                     disabled_xml(current["xml"]) == disabled_xml(before["xml"]))))
            if not same_definition:
                if not before.get("xml"):
                    raise ServiceError("TASK_SNAPSHOT_INCOMPLETE: cannot restore prior task")
                if self.ipc.running() and not transition.stopped:
                    raise ServiceError("ROLLBACK_INSTANCE_PROTECTED: original instance left running")
                self._call(transition, "register", xml=disabled_xml(before["xml"]))
                current = self.scheduler.query()
            should_run = transition.was_running and not self.ipc.running()
            if before.get("enabled") or should_run:
                if not current.get("enabled"):
                    self._call(transition, "enable")
            if should_run:
                self._call(transition, "run")
                deadline = self.clock() + self.start_timeout
                while not self.ipc.running() and self.clock() < deadline:
                    self.sleep(0.2)
                if not self.ipc.running():
                    raise ServiceError("ROLLBACK_START_UNCONFIRMED: original task restoration not confirmed")
            if not before.get("enabled"):
                self._call(transition, "disable")
        launch_path = self.paths.state.parent / "launch.json"
        if transition.launch_before is None:
            launch_path.unlink(missing_ok=True)
        else:
            # Restore exact prior bytes; launch state is private and never logged.
            launch_path.parent.mkdir(parents=True, exist_ok=True)
            launch_path.write_bytes(transition.launch_before)
        observed = self.scheduler.query()
        running = self.ipc.running()
        if (bool(observed.get("registered")) != bool(before.get("registered"))
                or bool(observed.get("enabled")) != bool(before.get("enabled"))
                or running != transition.was_running
                or (before.get("registered") and
                    (observed.get("description") != before.get("description") or
                     definition_identity(observed.get("xml")) != definition_identity(before.get("xml"))))):
            raise ServiceError("ROLLBACK_STATE_UNCONFIRMED: observed final state differs from snapshot")
        return state_summary(observed, running)

    def _transition(self, command, config):
        try:
            if getattr(self.scheduler, "sid", self.ipc.sid) != self.ipc.sid:
                raise SchedulerError("TASK_IDENTITY_MISMATCH", command, "snapshot")
            task = dict(self.scheduler.query())
            running = self.ipc.running()
            launch = self.paths.state.parent / "launch.json"
            before = launch.read_bytes() if launch.is_file() else None
        except Exception as exc:
            raise LifecycleError(command, exc, state_summary(), "not_attempted") from None
        transition = Transition(task, running or task.get("state") in (2, 4), self.ipc.sid, before,
                                task.get("description"), task.get("xml"))
        try:
            if command in ("start", "restart") and running and not task.get("registered"):
                raise ServiceError("UNMANAGED_INSTANCE: stop the foreground instance explicitly before starting a task")
            if command in ("start", "restart", "uninstall-service") and task.get("registered") and not task.get("xml"):
                raise ServiceError("TASK_SNAPSHOT_INCOMPLETE: no mutation without a restorable task snapshot")
            if command == "start":
                return self._start(transition, config)
            if command == "restart":
                stopped = self._stop(transition)
                return dict(self._start(transition, config), stop_result=stopped)
            stopped = self._stop(transition)
            if command == "uninstall-service":
                if self.scheduler.query().get("registered"):
                    self._call(transition, "delete")
            return dict(self.status(), stop_result=stopped)
        except (Exception, KeyboardInterrupt) as exc:
            if not transition.dirty:
                state, outcome, cleanup = state_summary(task, running), "not_needed", None
            elif isinstance(exc, SchedulerError) and exc.kind in ("PROCESS_START_FAILED", "PROCESS_TIMEOUT", "PROCESS_CANCELLED"):
                # The transport cannot be relied on. Do not repeat a blocked or
                # indeterminate operation to try to obtain cleanup privileges.
                state, outcome, cleanup = state_summary(), "unavailable", "TRANSPORT_UNAVAILABLE"
            else:
                try:
                    state, outcome, cleanup = self._rollback(transition), "restored", None
                except Exception as failed:
                    state, outcome = self._observe(failed), "failed"
                    cleanup = str(failed) if isinstance(failed, ServiceError) else type(failed).__name__
            error = LifecycleError(command, exc, state, outcome, cleanup)
            error.before_state = state_summary(task, running)
            error.identity_sid = transition.identity_sid  # Memory only; never included in CLI/log text.
            error.identity_verified = bool(task.get("registered"))
            raise error from None

    def execute(self, command, config=None):
        if command == "status":
            return self.status()
        if command not in ("start", "restart", "stop", "uninstall-service"):
            raise ServiceError("Unknown lifecycle command")
        try:
            with self.ipc.lock("control", timeout=5):
                return self._transition(command, config)
        except LifecycleError:
            raise
        except Exception as exc:
            raise LifecycleError(command, exc, state_summary(), "not_attempted") from None
