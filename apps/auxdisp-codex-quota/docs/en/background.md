# auxdisp-codex-quota — Windows background operation

[中文版](../zh/background.md) | [Configuration and previews](usage.md)

## Install and start

The following interface applies to an installed distribution. Install and configure `codex-auth` for the current Windows user and prepare an accessible Turing USB 5.2-inch device.

```powershell
pip install auxdisp-codex-quota
auxdisp-codex-quota start
auxdisp-codex-quota status
auxdisp-codex-quota stop
auxdisp-codex-quota restart
```

Package installation only installs Python code and the CLI. The first `start` registers and launches `auxdisp-codex-quota-<current user SID>`. Its action uses the absolute installed `pythonw.exe` path and the package's internal entry point. It needs no source checkout, uv cache, or open PowerShell window.

Since 0.1.2, Python Direct COM manages scheduled tasks and supports standard `pip --user`, venv and uv tool installations. Windows installs pywin32; access denial is reported as an error.

Since 0.1.2, background tasks use `-E -P -m auxdisp_codex_quota._background`: interpreter environment variables such as `PYTHONPATH` are ignored and the working directory is excluded from module search, while standard user-site packages remain available to load the application and its dependencies. The user site, including its `.pth` files and customization modules, remains a trusted part of the Python installation; this is not full `-I` isolation. Global, standard `pip --user`, and virtual-environment installations are supported; keep the chosen interpreter environment available.

Versions through 0.1.1 use `-I`, which hides user-site packages; use a virtual environment or uv tool environment for background operation with those releases. After installing a version containing the fix, `start` or `restart` updates the existing task arguments without deleting the task. Legacy arguments still undergo the full ownership checks.

The task runs only while the current user is logged in and starts at logon, without administrator privileges or automatic elevation. If Windows policy denies task registration, the command returns an actionable error instead of elevating.

Repeated `start` retains the running instance. It checks the package version, task interpreter, and launch parameters; a package version upgrade or migration to another Python installation gracefully stops the old instance and updates the same task. Use `restart` after configuration changes. Repeat an explicit configuration path when starting or restarting:

```powershell
auxdisp-codex-quota start --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota restart --config C:\Users\Me\auxdisp-config.toml
```

## Update the package

Run in the original installation environment, retaining existing configuration:

```powershell
auxdisp-codex-quota stop
pip install --upgrade auxdisp-codex-quota
auxdisp-codex-quota start
```

An upgrade does not restart a running process; use `restart` if already upgraded while running. Configuration changes also need `restart`. Repeat `--config` on the final `start` or `restart` for custom files. See [troubleshooting](troubleshooting.md).

## Configuration, logs, and status

```text
%LOCALAPPDATA%\auxdisp-codex-quota\
├── config.toml
├── logs\service.log
└── state\
    ├── service.json
    ├── launch.json
    └── last-stop.json
```

Configuration priority is explicit `--config`, the current user's data-directory `config.toml`, then built-in defaults. Launch-directory configuration is never read implicitly; developers can use `--config ./config.toml`. When the default file is missing, the first `start` creates a comment-only file using the defaults, without overwriting existing configuration.

`start` resolves the native `codex-auth.exe` path, including flat and nested official npm installations, and passes its absolute location to the background host. A configured native path also works:

```toml
[collector]
executable = 'C:\Tools\codex-auth.exe'
```

A successfully resolved command is recorded in `state/launch.json` for reuse when a later shell has a reduced PATH. Changing the command or configuration file requires a fresh check. Collection runs under the current user, never SYSTEM, and only executes `list --api --json`.

File logs rotate at 1 MiB with three backups. Logs and health state contain no tokens, raw account JSON, email addresses, or account names. State records only an instance identifier, diagnostic PID, heartbeat, last successful collection time, and observed USB connection state. The PID is never a termination target.

`status` reports `registered`, `enabled`, `process_running`, `usb_connected`, and `last_success_at` separately as JSON. A cross-process named mutex proves runtime liveness; a PID file does not. USB health becomes `null` when the runtime is stopped or the heartbeat is older than ten seconds. Boolean USB status is the last observed transport state, not continuous hardware probing. Headless foreground output also reports `null` for USB.

## Stop and recovery

`stop` disables the task before sending the user's named stop Event. The runtime cancels the active collector process tree and waits for display-resource cleanup. Repeated stop is safe when no instance is running.

Graceful shutdown has a 30-second controller deadline. Only after that deadline may Task Scheduler terminate this owned task, followed by up to five seconds to confirm exit. Forced shutdown is reported and recorded in `state/last-stop.json`. No arbitrary Python or Codex PID is killed; a hung foreground instance with no registered task cannot be force-killed through this fallback.

The task ignores duplicate instances, has no long-running execution limit, permits battery operation, does not stop when idle ends, and starts when available. Unexpected process exits are retried at one-minute intervals, at most three times. Existing USB reconnection and stale-data behavior handle disconnections and API timeouts without restarting the host. Actual resume and scheduler recovery behavior still requires system acceptance.

## Foreground debugging and removal

```powershell
auxdisp-codex-quota run
auxdisp-codex-quota run --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota run --demo --headless preview.png --duration 60
auxdisp-codex-quota --preview preview.png
auxdisp-codex-quota --inspect
```

Omitting the command remains compatible with foreground `run`. Foreground and background Windows runtimes share the user's instance mutex. Previews and inspection do not start a display runtime. Existing preview, inspect, demo, fixture, headless, and duration flags remain available; they cannot be combined with management commands.

Before uninstalling the Python package:

```powershell
auxdisp-codex-quota stop
auxdisp-codex-quota uninstall-service
pip uninstall auxdisp-codex-quota
```

`uninstall-service` stops the instance before deleting this user's task, preserving personal configuration, logs, and diagnostics. Installing or upgrading a package does not modify tasks; run `start` or `restart` afterward to reconcile the current installation.
