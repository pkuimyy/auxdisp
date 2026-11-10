# Configuration and development

[中文版](../zh/usage.md) | [Overview](README.md)

## Data source

The only account command is `codex-auth list --api --json`, using [codex-auth JSON API schema 1](https://github.com/Loongphy/codex-auth/blob/main/docs/json-api.md). The app never passes `--active` or runs account switching, reset, or removal commands. Unknown fields are ignored; unsupported schema versions produce an error while keeping history. The app does not read or store authentication tokens.

Install and configure `codex-auth` independently. On Windows, npm installations resolve the official native `codex-auth.exe` from flat or nested dependencies so timeout and shutdown can terminate its process tree. For other installations, configure the native executable's full path. Missing commands, invalid JSON, timeouts, and nonzero exits produce safe error codes without echoing raw stdout/stderr.

## Local configuration

Copy `config.example.toml` to `config.toml` once, without overwriting an existing configuration. The current directory's `config.toml` is loaded automatically, or use `--config <path>`. Git ignores this file; it holds display settings and stable account IDs, not tokens.

| Setting | Default |
|---|---|
| `collector.executable` | `codex-auth` |
| `collector.refresh_seconds` | 60 seconds |
| `collector.timeout_seconds` | 20 seconds |
| `rotation.seconds` | 15 seconds |
| `display.orientation` | `landscape` (1280×720 only) |
| `display.brightness` | 30% |
| `display.reconnect_seconds` | 5 seconds |
| `render.thresholds` | `[75, 50, 25]` |
| `render.font` | Empty; use system fonts |
| `logging.level` | `INFO` |

Percentages display up to two decimal places. Filled segments use the actual remaining percentage, rounded upward to one segment per 10%; unknown data is distinct from zero. Durations 300 and 10080 identify 5-hour and 7-day quotas. Other durations remain in the model and are not misclassified.

The compact TUI uses a fixed 1280×720 canvas. Account identity, plan, ACTIVE/INACTIVE, STALE, date, and time share one header line. Quota rows align the window, ten thin segments, percentage, and reset time in columns. Bars stay 21px high. The fixed footer shows the page index, READ ONLY, API status, and LAST OK, with natural whitespace below the resource row.

Two font sizes are used: 44px for account names and percentages, and 24px for date/time, resource values, labels, status, and other information. The default is monospace, with a system CJK fallback at the same size for Chinese names; `render.font` accepts a font file. Long identities and status details are ellipsized within their reserved regions. CREDITS, RESET CARDS, and NEXT EXPIRY currently display `N/A`; resource fields are not connected, so these placeholders do not indicate balances or card counts.

Inspect normalized data and stable `account_key` values with this read-only command. Its output contains account identities and should not be shared publicly:

```powershell
uv run --locked --no-sources auxdisp-codex-quota --inspect
```

Explicitly configure an account known to have no 5-hour limit:

```toml
[accounts."complete stable account_key here"]
unlimited_windows = [300]
```

Policies match exact stable IDs, never email suffixes, missing windows, or `secondary=null`. Missing windows default to `UNAVAILABLE`; only explicit policies show `NOT LIMITED`.

## Offline and headless modes

```powershell
# Three synthetic previews; no real accounts or USB
uv run --locked --no-sources auxdisp-codex-quota --preview previews/dual.png
uv run --locked --no-sources auxdisp-codex-quota --preview previews/single.png --account-index 1
uv run --locked --no-sources auxdisp-codex-quota --preview previews/error.png --simulate-error

# Rotate demo accounts for 60 seconds, writing only the latest PNG
uv run --locked --no-sources auxdisp-codex-quota --demo --headless previews/latest.png --duration 60
```

`--fixture <JSON path>` replaces the bundled synthetic accounts. `--headless <PNG path>` alone still collects real accounts, replacing only USB output; add `--demo` to run fully offline. `--duration` bounds integration runs. Without it the app runs until Ctrl+C, then releases resources.

## Implementation

| Module | Responsibility |
|---|---|
| `collector.py` | Read-only command, process-tree timeout/cancellation, one worker and one result slot |
| `model.py` | Protocol parsing, immutable account snapshots, failure merging, stable-ID rotation |
| `config.py` | TOML validation and explicit account policies |
| `render.py` | Page models, fixed clock position, text clipping, ten-segment bars |
| `display.py` | Independent USB worker, latest-frame slot, reconnect and duplicate suppression |
| `runtime.py` | Collection cadence, rotation, minute clock, and visible-page deduplication |
| `cli.py` | Normal startup, previews, inspection, and bounded runs |

Collection, scheduling, and USB output are independent. The clock remains visible without accounts. Global failures preserve all history; per-account failures preserve that account's history and show `STALE`. Request success time is stored separately from `usage.updated_at`. Reordering retains the current stable ID; removal prefers the next surviving account in the previous order.

## Tests and limitations

Run in this project directory:

```powershell
uv sync --locked --all-groups --no-sources
uv run --locked --no-sources ruff check src tests
uv run --locked --no-sources pytest
uv build --no-sources
```

App CI is independent and installs the released driver from PyPI, with no monorepo path dependency. Tests and previews use synthetic accounts and fake devices. See [Local development](../../../../docs/en/development.md) for per-project environments and the shared cache.

Only one Turing USB 5.2-inch display in landscape is supported. Reconnection retries the latest frame; OS USB calls may briefly block the display worker. A 75-second integration run does not establish long-duration stability. Do not add GUI, account management, animation, or other screen models before initial acceptance.
