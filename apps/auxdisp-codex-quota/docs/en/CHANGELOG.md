# auxdisp-codex-quota — Changelog

[中文版](../zh/CHANGELOG.md)

### Unreleased

- Adopt the compact TUI v3 header, column-aligned thin quota bars, and fixed footer.
- Use 44px for account names and percentages and 24px for all other text, with monospace defaults, CJK fallback, and clipping.
- Keep the page index, READ ONLY, API status, and LAST OK in the footer; remove collection/rotation interval hints.
- Add an inline resource row with explicit `N/A` placeholders, preserving collection, rotation, and USB behavior.

### 0.1.0

- Depend on the released auxdisp-driver from PyPI.
- Add read-only collection, duration-based quotas, historical snapshots, and account rotation.
- Add a fixed clock, ten-segment bars, offline previews, and USB reconnection.
- Add synthetic-data, failure-recovery, and installation tests.
