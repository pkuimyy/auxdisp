# auxdisp-codex-quota — Changelog

[中文版](../zh/CHANGELOG.md)

### 0.1.4

- Display reset-card counts and per-card status, expiry time, and time remaining; rotate card pages independently and label account and card-page counters explicitly.
- Add quota reset countdowns and remove the CREDITS placeholder from the screen.
- Clear the screen and set brightness to zero on normal stop or foreground Ctrl+C; restore configured brightness on startup and report failed or unconfirmed screen-off separately.
- Use explicit CLI subcommands and show help without arguments. `status` now prints readable text; use `status --json` for structured output.
- Generate synthetic PNGs with `preview`, defaulting to `auxdisp-codex-quota-preview.png` in the current directory, with `--output` support. Move developer options out of the public CLI into a source script.

### 0.1.3

- Streamline user documentation; remove local acceptance and migration reports from public docs and source distributions.
- Align Chinese and English navigation, support boundaries and release-note links; runtime behavior is unchanged.

### 0.1.2

- Use Python Direct COM as the sole runtime backend; remove the PowerShell Bridge/encoded commands with no automatic fallback, while retaining legacy task identity/argument compatibility.
- Use -E -P for standard pip --user startup while excluding the working directory and PYTHONPATH; require pywin32>=311 only on Windows.
- Harden disabled registration, verified activation, snapshot compensation and explicit residual/unknown-state reporting; restore snapshots whose default Enabled XML node Windows omits.
- Add safe error classification, native failure-recovery acceptance and real CLI installation checks for wheel/venv, uv tool and standard user-level pip.

### 0.1.1

- Resolve Task Scheduler principal names to SIDs before ownership comparison, accepting equivalent current-user names while rejecting unresolved identities.
- Distinguish identity resolution, identity mismatch, management marker, and action errors while retaining every task safety check.
- Add native Windows identity regression tests and an opt-in real temporary-task lifecycle test.

### 0.1.0

- Add current-user Windows scheduled tasks and start/stop/status/restart/run/uninstall-service commands.
- Add instance mutexes, graceful-stop events, collection cancellation, bounded crash retries, and rotating user logs.
- Default configuration to the current user's data directory; development-directory files require explicit `--config`.
- Adopt the compact TUI v3 header, column-aligned thin quota bars, and fixed footer.
- Use 44px for account names and percentages and 24px for all other text, with monospace defaults, CJK fallback, and clipping.
- Keep the page index, READ ONLY, API status, and LAST OK in the footer; remove collection/rotation interval hints.
- Add an inline resource row with explicit `N/A` placeholders, preserving collection, rotation, and USB behavior.

- Depend on the released auxdisp-driver from PyPI.
- Add read-only collection, duration-based quotas, historical snapshots, and account rotation.
- Add a fixed clock, ten-segment bars, offline previews, and USB reconnection.
- Add synthetic-data, failure-recovery, and installation tests.
