# auxdisp-codex-quota — Changelog

[中文版](../zh/CHANGELOG.md)

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
