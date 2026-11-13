# auxdisp-codex-quota — Configuration and previews

[中文版](../zh/usage.md) | [Getting started](https://github.com/pkuimyy/auxdisp/blob/main/apps/auxdisp-codex-quota/docs/en/README.md) | [Background management](background.md)

## Configuration location

Priority: explicit `--config <path>` → `%LOCALAPPDATA%\auxdisp-codex-quota\config.toml` → built-in defaults. The working directory is not searched. The first `start` creates a comment-only default file without overwriting existing settings.

```powershell
notepad "$env:LOCALAPPDATA\auxdisp-codex-quota\config.toml"
auxdisp-codex-quota restart
```

If the default file does not exist, create its directory and `config.toml`, or create a TOML file elsewhere and select it explicitly:

```powershell
auxdisp-codex-quota start --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota restart --config C:\Users\Me\auxdisp-config.toml
```

## Settings and defaults

| Setting | Default |
|---|---|
| `collector.executable` | `codex-auth` |
| `collector.refresh_seconds` | 60 s |
| `collector.timeout_seconds` | 20 s |
| `rotation.seconds` | 15 s |
| `display.orientation` | `landscape` (1280×720) |
| `display.brightness` | 30% |
| `display.reconnect_seconds` | 5 s |
| `render.thresholds` | `[75, 50, 25]` |
| `render.font` | Empty; use system fonts |
| `logging.level` | `INFO` |

Use this as a configuration starting point; omitted settings retain defaults. Brightness must be an integer from 0–100, intervals must be positive, and orientation only accepts `landscape`.

```toml
[collector]
executable = "codex-auth"
refresh_seconds = 60
timeout_seconds = 20

[rotation]
seconds = 15

[display]
brightness = 30
reconnect_seconds = 5

[render]
font = ""
thresholds = [75, 50, 25]
```

Use TOML single quotes for native Windows paths to avoid backslash escaping:

```toml
[collector]
executable = 'C:\Tools\codex-auth.exe'

[render]
font = 'C:\Windows\Fonts\consola.ttf'
```

This is an alternative example: merge fields into existing tables rather than repeating `[collector]` or `[render]` in one file. Sizes are fixed by code: 44px for identities/percentages and 24px elsewhere. Font paths change the typeface only. Defaults use monospace with a system CJK fallback; long text is ellipsized.

## Explicit quota policies

Inspect normalized data and stable `account_key` values without USB:

```powershell
auxdisp-codex-quota --inspect
```

Output contains account identities; do not share it publicly. Only if you have an explicit basis for an account having no 5-hour limit, configure its complete stable ID:

```toml
[accounts."replace-with-exact-stable-account-key"]
unlimited_windows = [300]
```

Policies match stable IDs and accept 300 / 10080 minutes. Unlimited quotas are not inferred from email suffixes, `secondary=null`, or missing windows. Missing data displays `DATA UNAVAILABLE`, not zero.

## Offline and headless operation

```powershell
auxdisp-codex-quota --preview dual.png
auxdisp-codex-quota --preview weekly.png --account-index 1
auxdisp-codex-quota --preview error.png --simulate-error
auxdisp-codex-quota run --demo --headless latest.png --duration 60
```

These commands use synthetic accounts without real-account or USB access. `--account-index` is zero-based. `--fixture <JSON path>` accepts custom schema-1 data.

```powershell
auxdisp-codex-quota run --headless real-accounts.png --duration 65
```

**This command reads real accounts**, replacing only USB output with PNG. Images may contain names or emails; redact before sharing. Add `--demo` for fully offline operation. `--duration` bounds the run; otherwise use Ctrl+C.

## Data source and boundaries

Only executes `codex-auth list --api --json` ([JSON API schema 1](https://github.com/Loongphy/codex-auth/blob/main/docs/json-api.md)). Official Windows npm packages resolve their native exe automatically, including nested/flat layouts; other installations can configure a native path explicitly.

Windows are matched by duration, not primary/secondary order. API ERROR can indicate a failed command or current-account refresh. History stays in the running process’s memory; restarting does not restore quota snapshots. LAST OK is the overall successful request time, not each account’s `usage.updated_at`.

The quota table shows reset date/time in the local timezone under `RESET AT`, and time remaining under `RESET IN`. Once the reset time is reached, `DUE` remains until collection confirms the actual quota. Ten-segment bars round remaining percentages upward; displayed values have up to two decimal places.

The screen does not show `CREDITS`. `RESET CARDS` reads `usage.reset_credits`. Valid zero values show `0`; missing or invalid values show `N/A`. Counts are not inferred from card details.

Card details read `usage.reset_credit`, retaining each card's title, status, expiry date/time (`EXPIRES AT`), and time remaining (`EXPIRES IN`). Cards are sorted by earliest expiry; missing or invalid expiry times sort last and show `--`. Expired cards show `EXPIRED`. Each page holds up to three cards; all card pages rotate within one account rotation interval, with `RESET CARDS PAGES 1/1` on the right and `ACCOUNT 1/3` in the footer. Card-page changes affect only the card region, keeping the selected account and upper quota bars intact. Accounts still rotate at the configured interval; quota collection and countdowns update independently. Missing details show `NO CARD DETAILS` or `N/A`, which does not imply a zero count.

Time remaining uses days/hours or hours/minutes, with `1m` for the final partial minute. Countdowns update with the display and never consume cards. Failed refreshes retain historical quotas and cards with `STALE`; successful refreshes replace that history.

For development environments, tests, and independent builds, see [local development](https://github.com/pkuimyy/auxdisp/blob/main/docs/en/development.md); for failures, see [troubleshooting](troubleshooting.md).
