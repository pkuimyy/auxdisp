"""Current-user Task Scheduler registration through a fixed, hidden COM bridge."""

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

from . import __version__
from .paths import APP_ID
from .win32 import ServiceError, current_sid, system_directory


NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
MARKER = f"{APP_ID} managed background task v1"


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
            "-I", "-m", "auxdisp_codex_quota._background", "--config", str(self.config),
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
            ("AllowStartOnDemand", "true"), ("Enabled", "true"), ("Hidden", "true"),
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


# All untrusted strings travel as JSON on stdin, never as PowerShell source.
BRIDGE = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
function Error-Code($exception) {
    while ($null -ne $exception.InnerException) { $exception = $exception.InnerException }
    return ($exception.HResult -band 0xffffffffL)
}
function Get-TaskOwnershipError($definition, [string]$sid, [string]$marker) {
    # COM may return a SID, local username, or DOMAIN\username for the same user.
    # Never fall back to comparing names if Windows cannot resolve the identity.
    try {
        $identity = [string]$definition.Principal.UserId
        if ([string]::IsNullOrWhiteSpace($identity)) { return 'TASK_IDENTITY_UNRESOLVED' }
        if ($identity.StartsWith('S-', [StringComparison]::OrdinalIgnoreCase)) {
            $principalSid = [System.Security.Principal.SecurityIdentifier]::new($identity).Value
        } else {
            $account = [System.Security.Principal.NTAccount]::new($identity)
            $principalSid = $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
        }
    } catch { return 'TASK_IDENTITY_UNRESOLVED' }
    if ($principalSid -ne $sid) { return 'TASK_IDENTITY_MISMATCH' }
    $description = [string]$definition.RegistrationInfo.Description
    if (-not $description.StartsWith($marker + ' ', [StringComparison]::Ordinal)) {
        return 'TASK_MARKER_MISMATCH'
    }
    if ($definition.Actions.Count -ne 1) { return 'TASK_ACTION_MISMATCH' }
    $arguments = [string]$definition.Actions.Item(1).Arguments
    if (-not $arguments.StartsWith('-I -m auxdisp_codex_quota._background ', [StringComparison]::Ordinal)) {
        return 'TASK_ACTION_MISMATCH'
    }
    return $null
}
try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $folder = $scheduler.GetFolder('\')
    $task = $null
    try { $task = $folder.GetTask($request.name) }
    catch {
        $code = Error-Code $_.Exception
        if ($code -ne 0x80070002L -and $code -ne 0x8004130fL) { throw }
    }
    # Refuse to modify an unrelated task even if its name collides.
    if ($null -ne $task) {
        $definition = $task.Definition
        $ownershipError = Get-TaskOwnershipError $definition $request.sid $request.marker
        if ($null -ne $ownershipError) {
            [Console]::Write((@{error=$ownershipError} | ConvertTo-Json -Compress))
            exit 1
        }
    }
    switch ($request.operation) {
        'register' { $null = $folder.RegisterTask($request.name, $request.xml, 6, $request.sid, $null, 3, $null) }
        'enable' { if ($null -ne $task) { $task.Enabled = $true } }
        'disable' { if ($null -ne $task) { $task.Enabled = $false } }
        'run' { if ($null -eq $task) { throw 'Missing task' }; $null = $task.Run($null) }
        'end' { if ($null -ne $task) { $null = $task.Stop(0) } }
        'delete' { if ($null -ne $task) { $null = $folder.DeleteTask($request.name, 0) } }
        'query' {
            if ($null -eq $task) { [Console]::Write('{"registered":false}'); exit 0 }
            $result = @{
                registered = $true; enabled = [bool]$task.Enabled; state = [int]$task.State
                last_result = [long]$task.LastTaskResult
                description = $task.Definition.RegistrationInfo.Description
                python = $task.Definition.Actions.Item(1).Path
            }
            [Console]::Write(($result | ConvertTo-Json -Compress)); exit 0
        }
        default { throw 'Unknown operation' }
    }
    [Console]::Write('{}')
} catch {
    $code = Error-Code $_.Exception
    [Console]::Write((@{error='TASK_SCHEDULER_FAILED'; code=$code} | ConvertTo-Json -Compress))
    exit 1
}
"""


class TaskScheduler:
    def __init__(self, sid=None, runner=None):
        self.sid = sid or current_sid()
        self.name = f"{APP_ID}-{self.sid}"
        self.runner = runner or subprocess.run

    def call(self, operation, **values):
        powershell = Path(system_directory()) / "WindowsPowerShell/v1.0/powershell.exe"
        encoded = base64.b64encode(BRIDGE.encode("utf-16-le")).decode("ascii")
        payload = dict(operation=operation, name=self.name, sid=self.sid, marker=MARKER, **values)
        try:
            result = self.runner(
                [str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
                input=json.dumps(payload, ensure_ascii=True), capture_output=True, encoding="utf-8", errors="replace",
                timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            response = json.loads(result.stdout.lstrip("\ufeff"))
            if not isinstance(response, dict):
                raise ValueError("Invalid bridge response")
            if result.returncode or "error" in response:
                ownership_errors = {
                    "TASK_IDENTITY_UNRESOLVED": "Task principal could not be resolved to a SID",
                    "TASK_IDENTITY_MISMATCH": "Task principal belongs to a different Windows user",
                    "TASK_MARKER_MISMATCH": "Task description does not contain the expected management marker",
                    "TASK_ACTION_MISMATCH": "Task actions do not match the managed background entry point",
                }
                error = response.get("error")
                if error in ownership_errors:
                    raise ServiceError(f"{error}: {ownership_errors[error]}; no changes made")
                if response.get("error") == "TASK_OWNERSHIP_MISMATCH":
                    raise ServiceError("Task name is occupied by an unmanaged task; no changes made")
                raise ServiceError(
                    f"Task Scheduler {operation} failed (code {response.get('code', 'unknown')}); "
                    "check current-user task permissions and Windows policy; no elevation was attempted"
                )
            return response
        except (OSError, subprocess.TimeoutExpired, ValueError):
            raise ServiceError(f"Task Scheduler {operation} could not complete; check Windows policy") from None

    def query(self):
        return self.call("query")
