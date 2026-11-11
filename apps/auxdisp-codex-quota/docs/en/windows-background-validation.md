# auxdisp-codex-quota — Windows background security validation

[中文版](../zh/windows-background-validation.md) | [Troubleshooting](troubleshooting.md)

Date: 2026-11-11, Asia/Shanghai. Baseline: PyPI 0.1.1, Windows/Python 3.13.7, uv tool installation. The local diagnostic build retains 0.1.1 metadata and is **not a new PyPI release**. Earlier uncommitted user-site compatibility changes remain separate from this investigation.

This is the previous phase's historical snapshot. Subsequent work resolved its lifecycle xfail and added a Windows-only pywin32 dependency/candidate adapter. See the [lifecycle hardening report](windows-lifecycle-hardening.md) for current implementation, counts and remaining acceptance. The old test counts and dependency statements apply only to that earlier phase.

## Conclusion

**Recommendation 2: prepare a separate Python Direct COM migration; do not replace the production backend yet.** A single read-only pywin32 probe successfully connected to Task Scheduler. This establishes limited technical feasibility, not authorization for writes or proof of a particular security-product rule. The rationale is fewer transport layers and explicit HRESULTs, not circumvention. Stop if policy denies COM access.

The user's observed security popup is relevant evidence, but no correlated rule/event identifies its exact cause. Installed security-product metadata includes YunMai and Windows Defender; that alone cannot attribute the block. The old generic error does not establish a Task Scheduler permission failure.

## Audit and diagnostics

```text
CLI → ServiceController → TaskScheduler.query()/call()
    → hidden encoded PowerShell → Schedule.Service → Connect → root folder
    → exact task lookup → ownership checks → operation → JSON → Python parsing
```

The fixed Bridge source is UTF-16LE/Base64 encoded; untrusted request values travel as stdin JSON rather than PowerShell source. Execution has a 20-second timeout and captures output. Version 0.1.1 collapses process creation errors, timeout, invalid JSON and non-object responses into `could not complete`. A valid COM error response normally follows a different path. Encoding provides no authorization.

`start` loads configuration and resolves the collector, queries the task, stops a changed running instance, registers if needed, enables, runs if needed, waits for the mutex and reports status. `restart` stops first. `stop` disables first, signals the stop Event and, if necessary, terminates only the verified task. The host/foreground path does not register tasks.

The diagnostic patch separates `PROCESS_START_FAILED`, `PROCESS_TIMEOUT`, `PROCESS_EXIT_FAILED`, `INVALID_BRIDGE_RESPONSE`, `ACCESS_DENIED` (explicit HRESULT 0x80070005), and `COM_CALL_FAILED`. It retains distinct identity, marker and action errors. Bridge phases are create_com, connect, get_root, get_task, ownership and task_operation. Only known phases and integer codes cross the error boundary; DEBUG logs contain operation, exit code and output lengths, never command lines, raw streams or account data. No automatic retry, elevation or unsupported `POLICY_RESTRICTED` inference is added.

## Evidence and limits

| Evidence | Result |
|---|---|
| User report | Security popup observed, no permission to allow it; no correlated rule/event available |
| Earlier development observation | PowerShell process creation WinError 5 occurred, without reliable correlation to this user incident |
| Defender / AppLocker logs | Read unavailable with a generic exception; not proof of access denial or absent events |
| CodeIntegrity log | No python/powershell/auxdisp matches in the latest 80 entries over two days; not an exhaustive audit |
| One Direct COM probe | Initialized COM, connected, obtained root and queried the exact current-user task; task absent |
| Real task properties | Not read because that task was absent; covered by implementation/Mocks, not claimed as native acceptance |

No known-blocked encoded PowerShell was rerun. Successful read-only access does not establish write permission or exclude task-specific ACL failures. A security-product versus process-policy attribution still requires administrator-provided correlated evidence; Python transport faults also remain possible.

## Technical comparison

| Dimension | PowerShell Bridge | Direct COM candidate |
|---|---|---|
| Layers | Python → hidden PowerShell → COM → JSON | Python → COM |
| Dependencies | System PowerShell | Windows-only pywin32 dependency if adopted |
| Errors | Process, transport and COM failures | HRESULT/SCODE directly available, still requiring redaction |
| Permissions | Current-user rights and process policies | Same Windows rights; no additional permissions |
| Time bounds | 20-second child-process boundary | Synchronous COM needs a separate bounded-call/cleanup design |
| Safety | SID, marker, action checks and IPC | All must be retained; probe is not a management backend |
| Writes | Existing implementation, not tested here | APIs support them; none exercised here |

PyPI metadata: pywin32 312 requires Python >=3.9 and provides CPython 3.11/3.12/3.13 Windows x86/x64/ARM64 wheels. Only 3.13 x64 was executed. comtypes 1.5.0 requires Python >=3.9 and has a pure Python wheel; installed but not exercised as a COM backend. Neither dependency was added to runtime metadata or uv.lock. No global post-install or administrator registration was needed for the pywin32 read-only probe.

Primary references: [Microsoft TaskService](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskservice), [pywin32](https://github.com/mhammond/pywin32), [comtypes](https://github.com/enthought/comtypes), [pywin32 on PyPI](https://pypi.org/project/pywin32/), [comtypes on PyPI](https://pypi.org/project/comtypes/). Available wheels do not establish execution acceptance for every version/architecture. Do not switch libraries to seek permissions after an explicit policy denial.

## Regression and installation

Run from the app directory with its Python 3.13 verification environment:

```powershell
./.venv-wheel/Scripts/python.exe -I -m pytest tests -q -W error --tb=short -k 'not bridge_normalizes_identity and not fixed_scheduler_bridge_is_valid_powershell and not task_xml_is_accepted_by_native_com and not real_scheduler_bridge_queries and not real_registered_task_lifecycle' --junitxml ../../.artifacts/auxdisp-codex-quota-security/tests.xml
```

Result: **135 passed, 22 deselected, 1 xfailed**. Excluded tests execute PowerShell or real task lifecycles; they are not counted as passed. Real pywin32 identity lookup checked current SID, local name, qualified name, another SID and an unresolvable name without accessing tasks. Mocks cover ownership refusal, lifecycle, migration, missing tasks, access denial, unavailable service and safe diagnostics without elevation or duplicate instances. The probe only uses the exact GetTask name, never task enumeration or writes.

**Known gap:** if registration/enable succeeds but run is rejected or startup confirmation fails, ServiceController has no transactional rollback and can leave an enabled task. A strict xfail records the Mock reproduction. The no-unexpected-enabled-task criterion is not satisfied. A migration should register new tasks disabled, track prior state, roll back where permitted and report residual state if cleanup is denied, without repeatedly triggering a known block. No real task was used to reproduce this gap.

Wheel/sdist builds and content/license/index-dependency/document-link checks passed. The wheel was installed only into `.venv-wheel`; the formal uv tool installation was unchanged. Installed-module isolation checks, a synthetic preview and a two-second foreground demo/headless run passed from outside the source project, with temporary LOCALAPPDATA and no real accounts or USB. Runtime dependencies remain auxdisp-driver and Pillow; the driver came from the index. COM experiment dependencies installed successfully without being adopted by the application.

## Remaining authorized acceptance and migration proposal

Actual task registration/lifecycle/removal, survival after terminal closure, logon startup, crash recovery and USB unplug/replug are **BLOCKED_BY_POLICY (authorization unavailable; not attempted)** in this investigation. This is not a newly observed native failure, and earlier acceptance does not authorize current system writes.

A separate migration patch should provide an interchangeable COM adapter, bounded calls, shared identity/marker/action validation, transactional lifecycle cleanup, failure diagnostics and the installation matrix. An administrator-approved environment must validate task writes and failures before adoption and release. Stop if direct COM is prohibited; do not add circumvention or fallback routes.

Deliverables: diagnostics in `scheduler.py`, the explicit read-only experiment `scripts/probe_task_scheduler_com.py`, diagnostic/probe tests and the known-gap test. Safe local evidence is in ignored `.artifacts/auxdisp-codex-quota-security/`: `direct-com.json`, `event-metadata.json`, `tests.xml`, test builds and synthetic previews. No policy changes, real task mutations, formal-install replacement, commits, pushes or releases were performed.
