# auxdisp-codex-quota — Troubleshooting

[中文版](../zh/troubleshooting.md) | [Getting started](https://github.com/pkuimyy/auxdisp/blob/main/apps/auxdisp-codex-quota/docs/en/README.md) | [Background management](background.md)

## CLI not found after installation

```powershell
python -m pip show auxdisp-codex-quota
python -m auxdisp_codex_quota --help
Get-Command auxdisp-codex-quota -All
```

Ensure `python` and the installing `pip` belong to the same environment. If the module works but the CLI does not, add that environment’s Scripts directory to PATH or activate its virtual environment. Module commands such as `python -m auxdisp_codex_quota start` also work. If an environment was deleted, reinstall in a retained environment and run `start` to reconcile the task.

## codex-auth missing or no accounts

```powershell
Get-Command codex-auth -All
codex-auth list --api --json
```

Under the same Windows user running this app, follow [codex-auth](https://github.com/Loongphy/codex-auth) to install and configure accounts. Query output contains identities; do not share it. For `COMMAND_NOT_FOUND`, check PATH. `CONFIGURE_NATIVE_CODEX_AUTH_EXE` requires the native exe’s full path in configuration. See [configuration](usage.md) and restart after changes.

## USB not recognized

Check the Turing USB 5.2-inch model, VID `0x1CBE` / PID `0x0050`, and a data-capable cable. Other models are outside application support. Inspect the device and compatible interface driver in Windows Device Manager. `libusb-package` is a user-space library; successful installation does not establish correct Windows interface binding or access. `process_running=true` alone does not prove USB access.

See [supported devices](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/supported-devices.md).

## Connected but blank

```powershell
auxdisp-codex-quota status
Get-Content "$env:LOCALAPPDATA\auxdisp-codex-quota\logs\service.log" -Tail 50
auxdisp-codex-quota stop
auxdisp-codex-quota run
```

Check for zero brightness, landscape mode, and USB unavailable / transfer failed logs. `usb_connected` is the last observed transport state; `null` means unknown, stopped, or stale health, not a successful connection. Foreground `run` uses real accounts and USB; exit with Ctrl+C. Stop the background runtime first because they share an instance lock. Use `preview --output preview.png` to check rendering independently. USB reconnection retries the latest frame.

## API ERROR / STALE

Run `codex-auth list --api --json` as the current user and inspect refresh status, network, and authorization locally. The app does not log in, switch accounts, or consume reset cards. Timeouts, command failures, unsupported schemas, and per-account refresh failures show errors; available history is retained with STALE and does not persist across restarts. API OK does not promise every window, and LAST OK is not the source-data timestamp.

## UNAVAILABLE / DATA UNAVAILABLE

This means no usable data for that window, not an exhausted quota. Windows are matched by 300 / 10080 minutes; an account may supply only a 7-day window, even as primary. Set `unlimited_windows` only with an explicit basis for that policy, never to hide missing data.

## Background startup fails or unexpected restart

Use the error code to distinguish process creation, timeout, response parsing and COM failures. A generic error does not establish a security-software block; inspect Task Scheduler and system events for permission or policy failures.

An error reporting `rollback=failed/unavailable` or an unknown final state does not establish cleanup. Inspect `status` and the actual task in Task Scheduler before deciding how to recover.

Inspect `registered`, `enabled`, and `process_running` in `status`. For registration failures, check Task Scheduler availability, current-user task permissions, and policy; the app does not elevate. Ensure the task’s Python environment still exists with `pythonw.exe`, and codex-auth resolves. Run `start` after upgrades or environment migration to reconcile the task.

Use `auxdisp-codex-quota stop`: it disables logon startup and crash retries first. Closing a terminal or killing the process is different from stop. `restart` enables and launches it again. Use `uninstall-service` before uninstalling the package. For diagnostics and stop deadlines, see [background operation](background.md).

## Background exits immediately after a user-level pip installation

Background tasks in versions through 0.1.1 use `-I`, hiding user-site packages. The CLI can work while the background process cannot import the application, even before new logs are initialized. Check the installation location with `python -m pip show auxdisp-codex-quota`. Version 0.1.2 fixes this using `-E -P`. Use a virtual environment or uv tool environment with older releases; reinstalling Python is unnecessary. Once a fixed version is installed, run `start` / `restart` to update the existing task. See [background operation](background.md).

## Task ownership errors

Since 0.1.1, the app resolves Task Scheduler's `Principal.UserId` (SID, local username, or `DOMAIN\username`) to a SID through Windows identity APIs before comparing it with the current user. A matching task name or valid Description alone never establishes ownership. Older `TASK_OWNERSHIP_MISMATCH` errors may result from equivalent username/SID representations; the fix does not require deleting existing tasks.

| Error | Meaning |
|---|---|
| `TASK_IDENTITY_UNRESOLVED` | Windows cannot resolve the principal, or it is empty/invalid; management denied |
| `TASK_IDENTITY_MISMATCH` | Resolved SID belongs to another user; management denied |
| `TASK_MARKER_MISMATCH` | Description lacks the expected management marker; management denied |
| `TASK_ACTION_MISMATCH` | Actions do not contain exactly the expected background launch action; management denied |

Inspect the principal, Description, and arguments in Task Scheduler without changing the task. Do not delete tasks or bypass checks to hide the error. Retry with an installation containing the fix and report redacted error codes if it persists.

## Report a problem

Include OS, Python and both package versions, device VID/PID, the command, and redacted status/logs. Do not upload real emails, names, account_key values, auth files, raw codex-auth JSON, or unredacted screenshots. [GitHub Issues](https://github.com/pkuimyy/auxdisp/issues).
