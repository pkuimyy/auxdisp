"""Backend-neutral task definition and stable launch identity."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

from . import __version__
from .task_adapter import MARKER
from .win32 import ServiceError

NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


@dataclass(frozen=True)
class TaskSpec:
    sid: str
    python: Path
    config: Path
    executable: Path
    working_directory: Path

    @classmethod
    def installed(cls, sid, config, executable, working_directory):
        python = Path(sys.executable).resolve().with_name("pythonw.exe")
        if not python.is_file():
            raise ServiceError("pythonw.exe is unavailable in this Python installation")
        return cls(sid, python, config.resolve(), Path(executable).resolve(), working_directory.resolve())

    @property
    def arguments(self):
        return subprocess.list2cmdline([
            # -I also implies -s, hiding ordinary pip --user installations.
            # Keep environment (-E) and working-directory (-P) isolation while
            # allowing the interpreter's normal user site and its dependencies.
            "-E", "-P", "-m", "auxdisp_codex_quota._background", "--config", str(self.config),
            "--executable", str(self.executable),
        ])

    @property
    def description(self):
        identity = json.dumps([__version__, str(self.python), self.arguments, str(self.working_directory)],
                              ensure_ascii=True)
        return MARKER + " " + hashlib.sha256(identity.encode()).hexdigest()

    def xml(self):
        if not all(path.is_absolute() for path in (self.python, self.config, self.executable, self.working_directory)):
            raise ServiceError("Scheduled task paths must be absolute")
        ET.register_namespace("", NS)
        root = ET.Element(f"{{{NS}}}Task", version="1.2")

        def child(parent, tag, value=None, **attrs):
            element = ET.SubElement(parent, f"{{{NS}}}{tag}", attrs)
            element.text = value
            return element

        info = child(root, "RegistrationInfo")
        child(info, "Description", self.description)
        trigger = child(child(root, "Triggers"), "LogonTrigger")
        child(trigger, "Enabled", "true")
        child(trigger, "UserId", self.sid)
        principal = child(child(root, "Principals"), "Principal", id="CurrentUser")
        child(principal, "UserId", self.sid)
        child(principal, "LogonType", "InteractiveToken")
        child(principal, "RunLevel", "LeastPrivilege")
        settings = child(root, "Settings")
        for tag, value in (
            ("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
            ("StopIfGoingOnBatteries", "false"), ("AllowHardTerminate", "true"),
            ("StartWhenAvailable", "true"), ("RunOnlyIfNetworkAvailable", "false"),
            ("AllowStartOnDemand", "true"), ("Enabled", "false"), ("Hidden", "true"),
            ("ExecutionTimeLimit", "PT0S"),
        ):
            child(settings, tag, value)
        idle = child(settings, "IdleSettings")
        child(idle, "StopOnIdleEnd", "false")
        child(idle, "RestartOnIdle", "false")
        retry = child(settings, "RestartOnFailure")
        child(retry, "Interval", "PT1M")
        child(retry, "Count", "3")
        action = child(child(root, "Actions", Context="CurrentUser"), "Exec")
        child(action, "Command", str(self.python))
        child(action, "Arguments", self.arguments)
        child(action, "WorkingDirectory", str(self.working_directory))
        return ET.tostring(root, encoding="unicode")
