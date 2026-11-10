# auxdisp-codex-quota

[中文版](../zh/README.md)

Rotate remaining quotas for multiple Codex accounts on a Turing USB 5.2-inch display: 1280×720 landscape, a fixed date and clock, ten-segment bars, and explicit error states.

Requires Python 3.11+, `codex-auth` with accounts already configured, and an accessible USB device. `auxdisp-driver` is installed from PyPI. This application is ready for initial acceptance testing.

### Install and run

Installed distributions support a current-user Windows background task:

```powershell
auxdisp-codex-quota start
auxdisp-codex-quota status
auxdisp-codex-quota stop
auxdisp-codex-quota restart
```

Installation does not register a task; the first `start` does. Configuration defaults to `%LOCALAPPDATA%\auxdisp-codex-quota\config.toml`. See [Windows background operation and removal](background.md). This implementation does not publish a new PyPI release.

For source development, from `apps/auxdisp-codex-quota`:

```powershell
uv sync --locked --no-sources
uv run --locked --no-sources auxdisp-codex-quota run --config config.example.toml
```

Defaults: collect every 60 seconds, rotate every 15 seconds, and use 30% brightness. Stop with Ctrl+C. The only account command is `codex-auth list --api --json`; the app does not switch accounts or consume reset credits.

`config.toml` holds intervals, brightness, and explicit quota policies keyed by stable account ID, with no authentication tokens. Missing quotas display `UNAVAILABLE`; only explicitly configured windows display `NOT LIMITED`.

### Offline preview

```powershell
uv run --locked --no-sources auxdisp-codex-quota --preview preview.png
```

Previews default to synthetic accounts and access neither USB nor account data. See the [usage guide](usage.md) for configuration, additional preview scenarios, and testing.
