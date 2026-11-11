# auxdisp-codex-quota — Windows lifecycle hardening and candidate Direct COM adapter

[中文版](../zh/windows-lifecycle-hardening.md) | [Earlier investigation](windows-background-validation.md) | [Background operation](background.md)

This preserves the candidate phase and its authorized acceptance history. The PowerShell backend has since been removed, with real user-level pip/venv/uv tool CLI checks; see the [installation verification record](windows-installation-verification.md). Statements below about retaining the old default refer to that earlier phase.

Date: 2026-11-11, Asia/Shanghai. These are **unreleased source changes**. Local test distributions retain 0.1.1 metadata; PyPI 0.1.1 does not thereby gain these changes. No formal installation, user task or Windows policy was modified.

## Outcome and state transitions

The previous strict xfail now passes normally. New tasks register disabled and must pass ownership/launch verification before activation. Failures attempt snapshot restoration, reporting residual or unknown state if cleanup cannot complete. `DirectComTaskScheduler` is a candidate only: `ServiceController` still defaults to the PowerShell `TaskScheduler`, with no automatic selection or fallback.

**Proceed to authorized replacement acceptance, not an immediate default switch.** Mock, read-only and installation evidence is available; native task writes, logon/recovery and security-product acceptance remain unverified.

Under the control mutex, capture presence, enabled/Scheduler state, Description, XML, current-user SID, prior instance state and exact launch.json bytes. Identity and XML remain in memory, never CLI/log output. Queued/starting tasks are treated as possibly activated; no duplicate Run is submitted.

| Initial state | Successful transition | Failure target/report |
|---|---|---|
| Missing | register disabled → verify → enable → run → confirm | Reclaim this transition's activation and restore absence |
| Disabled, idle | enable → run → confirm | Restore prior disabled definition |
| Enabled, idle | run or wait for queued startup | Restore prior definition and enabled/idle state |
| Healthy, same configuration | Reuse instance without re-register/run | Preflight failures do not stop it |
| Running with changed configuration | snapshot → stop → disabled replacement → verify → enable/run | Restore original definition, enabled state and running capability where possible; not the original PID |
| restart | One initial snapshot → stop → start | Restore original task or report residual/unknown state |
| stop | disable → Event → bounded wait → end verified task if necessary | Restore enable flag where possible, without stopping the original instance again |
| uninstall-service | stop → delete owned task | Restore snapshot where possible |
| Unowned/unresolvable | Refuse | No mutation; unreadable state cannot be guessed |
| Transport failure/timeout/cancellation | No alternate backend or repeated cleanup attempts | Explicit unknown outcome, not assumed uncommitted |

Summaries distinguish missing, disabled, enabled, starting, running and unknown. `LifecycleError` exposes `final_state`, `rollback` and `cleanup_error`, plus in-memory `before_state`/identity when captured. Safe CLI text contains status/diagnostics, never XML, launch paths or account data. Rollback values are not_needed, restored (observed/verified), failed, unavailable, and not_attempted for pre-snapshot/control-lock failures. Unknown never means restored.

## Hardened failure paths

Registration, enable, Run and confirmation failures now trigger guarded compensation, including a write committed before the client receives an error. Enabling can itself activate a queued trigger; that activation is also reclaimed. Upgrade/restart failures restore the original definition and launch.json where possible. Cleanup denial/read failure/restoration failure preserves the primary error and reports final state without unbounded retries.

Healthy pre-existing instances survive preflight failures. Cleanup rechecks ownership plus Description/executable/arguments/working directory before touching the task; identity drift stops cleanup. Only this transition's possible activation may be stopped during rollback; arbitrary PIDs are never killed. An unregistered foreground instance must be explicitly stopped rather than silently replaced.

This is application-lock-protected best-effort compensation, not a Windows transaction. Non-cooperating external edits can race; identity changes cause refusal. Missing snapshots or denied cleanup reduce the guarantee to a clear final/unknown-state report.

## Adapter contract and policy

`task_adapter.py` defines the Protocol: sid, name, query(), call(operation, **values). Operations are a fixed set and snapshots are plain dictionaries. `register` receives validated disabled XML; enable/disable change task.Enabled; run uses task.Run; end uses task.Stop; delete uses folder.DeleteTask. Lifecycle code depends on neither PowerShell nor pywin32 types.

Both transports share marker/prefix/operation constants, ownership errors and response decoding. Python uses the platform SID resolver; PowerShell receives the same policy constants and retains native resolution. Every operation checks ownership, including incoming registration definitions. SID/local/qualified names and legacy -I arguments are supported; unresolved/other identities, missing markers and invalid action counts/arguments are refused.

The same Mock contract exercises both real adapter classes through simulated transport endpoints and injectable COM objects, including lifecycle and failure matrices. This is not native PowerShell or COM-write acceptance. The formal installation remains untouched.

## Candidate process, resources and limits

The candidate launches the same installation's Python with `-E -P -m auxdisp_codex_quota._scheduler_com_worker`; it never launches PowerShell/EncodedCommand or switches backend on failure. The worker checks the current SID and AuxDisp task namespace, initializes STA COM, performs one operation, releases local wrappers, uninitializes its apartment and exits.

Runtime metadata/lockfile now include `pywin32>=312; sys_platform == 'win32'`. Non-Windows does not install it, and COM imports remain lazy in the candidate worker. Missing dependencies produce COM_UNAVAILABLE; HRESULT/SCODE access denial and other COM failures retain safe phase/numeric diagnostics.

Communication timeout defaults to 20 seconds. A real Python-child test confirms subprocess.run kills and reaps its own timed-out child. Cancellation reports an unknown operation outcome. Process termination **does not undo server-side writes already submitted to Task Scheduler**. Process creation, OS termination/reaping and multi-operation command duration are not strict 20-second total bounds. There is no claimed synchronous COM RPC cancellation or service-side transaction cancellation.

Initialization failure does not uninitialize an apartment never acquired; operation failure still releases the acquired apartment. One read-only experiment through the actual candidate worker succeeded: the current-user task was absent. No task writes or other-user task reads were performed.

## Tests and installation

Windows/Python 3.13.7, after fixing the issue found during authorized native testing: **249 passed, 22 deselected, no xfail**. The earlier installed-wheel run passed 246; loading this fix into the verification environment added three XML-default regressions. Excluded PowerShell/alternate native tests are not counted as passed; candidate-native acceptance is recorded separately below. The earlier 135 passed/one xfail result is historical.

```powershell
./.venv-wheel/Scripts/python.exe -I -m pytest tests -q -W error --tb=short -k 'not bridge_normalizes_identity and not fixed_scheduler_bridge_is_valid_powershell and not task_xml_is_accepted_by_native_com and not real_scheduler_bridge_queries and not real_registered_task_lifecycle' --junitxml ../../.artifacts/auxdisp-codex-quota-lifecycle/tests.xml
```

Coverage includes first/repeated start, pre/post-commit registration/enable/Run errors, confirmation timeout, rollback success/denial/unknown outcomes, original-task restoration, healthy-instance protection, identity drift, both-adapter contracts, COM unavailable/nested HRESULT refusal, apartment cleanup, real child-timeout cleanup, user-site imports, the non-Windows foreground branch and offline rendering.

Wheel/sdist and module/license/Windows dependency-marker/document-link checks passed. The same wheel was installed into isolated UV_TOOL_DIR/UV_TOOL_BIN_DIR under repository artifacts. Candidate/pywin32 imports, synthetic preview and a two-second demo/headless run passed outside the source project without UV_CACHE_DIR. Formal tool directories/PATH were untouched; no real accounts or USB were accessed. Python 3.11/3.12, other architectures and native non-Windows installations still need matrix acceptance.

Ignored local evidence: `.artifacts/auxdisp-codex-quota-lifecycle/`, including tests.xml, readonly-direct-com.json, build files/logs, isolated tool environment and synthetic previews. Version metadata remains 0.1.1 solely for local verification.

## 2026-11-11: subsequently authorized native acceptance

The user explicitly authorized local validation. `scripts/validate_direct_com_lifecycle.py --allow-task-writes --root <local evidence directory>` used only uniquely named test tasks through the Direct COM candidate and synthetic accounts. No formal task, security policy or encoded PowerShell invocation was changed/executed.

| Native check | Result |
|---|---|
| Initial registration/enable/start | Passed; real instance and host health confirmed |
| Background survives control child exit | Passed; not a manual full-terminal-close acceptance |
| Repeated start / single instance | Passed; host instance identifier unchanged |
| status | Task/IPC state cross-checked with real host health |
| stop / restart / uninstall-service | Passed for test tasks |
| Running legacy -I task migration to -E -P | Passed |
| Failed replacement restores original running task | Passed after XML-default fix; original definition/running capability restored |
| Missing program fails new startup | Passed; no registered task or instance remained |
| Startup confirmation timeout after real --help exit | Passed; task/instance reclaimed |
| Final cleanup | Both initial failure and fixed run removed test tasks/instances and preserved the formal task query result |

The first run found that Windows omits the default Settings/Enabled=true node. The old disabled_xml() rejected that legitimate snapshot. It now inserts missing Settings/Enabled and explicitly sets false; three regressions cover omitted nodes/settings and running-task restoration. The initial failure was a code defect, not attributed to security software. Cleanup succeeded; the fixed native run passed.

The controller's state directory was isolated while the scheduled host used normal diagnostics. The script explicitly read real host health rather than treating the isolated controller's phase as the formal CLI phase. This validates **ServiceController plus the Direct COM candidate**; the formal CLI still defaults to PowerShell. Synthetic frames may reach the screen; no new manual visual/USB-unplug acceptance was performed.

Evidence: `.artifacts/auxdisp-codex-quota-lifecycle/native-acceptance/native-acceptance.json` (initial defect) and `native-acceptance-fixed/native-acceptance.json` (PASSED). No access-denial/security-block error was observed. This does not identify the earlier PowerShell-block rule.

## Next gate

Normal candidate-native writes and the failure recovery cases above are now covered locally. Remaining acceptance includes real stalled COM RPC/cancellation outcomes, access/cleanup denial (currently Mock), full terminal closure, logon startup, crash retries, sleep, USB unplug/replug and other installation/architecture matrices. Default replacement review is reasonable; do not claim complete system acceptance.

Stop here: no default switch, formal-user task changes, policy changes, PyPI release, commit or push. If access is denied, stop and report rather than rotate backends to seek permission.
