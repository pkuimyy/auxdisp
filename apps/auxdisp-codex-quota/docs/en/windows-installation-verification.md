# auxdisp-codex-quota — Direct COM and installed CLI verification

[中文版](../zh/windows-installation-verification.md) | [Background operation](background.md) | [Lifecycle history](windows-lifecycle-hardening.md)

Date: 2026-11-11, Asia/Shanghai. This records pre-release acceptance for 0.1.2; test wheels then temporarily retained 0.1.1 metadata. PyPI 0.1.1 does not thereby contain these fixes.

## Final implementation

The runtime PowerShell Bridge, EncodedCommand invocation and alternate backend are removed. Python Direct COM is the only/default backend. scheduler.py is a compatibility entry point exporting TaskScheduler as DirectComTaskScheduler plus TaskSpec/NS/marker; it contains no legacy implementation.

SID normalization, marker/action checks, legacy -I task recognition and migration remain. The Python worker retains bounded communication/cancellation handling; timeout does not undo committed service-side writes. Denial never triggers another backend. pywin32>=311 is Windows-only; native checks covered existing user version 311 and isolated version 312.

CI's PowerShell shell, documentation command fences and recognizing codex-auth npm .ps1 filenames are not runtime backends. The collector resolves those wrappers to a native exe without executing PowerShell.

## Actual installed-entry-point acceptance

The built wheel's real .exe CLI was used, without injecting a backend or replacing ServiceController. Each run refused an existing default task/instance, supplied synthetic configuration, created a temporary synthetic collector file and invoked start/status/repeated start/stop/restart/uninstall-service from outside the source project. Host health and a stable instance identifier verified survival after CLI exit and no duplicate process.

Each run deleted only the task it had created, confirmed no remaining instance, removed its test file, restored prior service/launch/last-stop state bytes and verified unchanged default config.toml. The CLI uses the fixed current-user task name, so acceptance used that name only after confirming absence; no existing task was overwritten. Diagnostic logs retain appended test records.

`scripts/validate_installed_cli.py` requires explicit --allow-default-task-test. It writes real tasks and may briefly display synthetic frames; it is not a default offline test.

| Installation | Actual entry point | pywin32 | Result |
|---|---|---|---|
| Wheel / venv | Wheel in .venv-wheel; generated Scripts CLI | 312 | All passed |
| uv tool | Same wheel in isolated UV_TOOL_DIR/UV_TOOL_BIN_DIR; generated CLI | 312 | All passed |
| Standard pip --user | System Python installs to the real user site; user Scripts CLI | 311 | All passed |

Environment: Windows, system CPython 3.13.7 x64, connected Turing USB 5.2-inch display. All three runs confirmed running/fresh health, phase=running, single instance, graceful stop/restart, task uninstall, no residual instance, unchanged default configuration and restored prior diagnostic state. The user-install task actually loaded the user site using system pythonw.exe, covering the previously failing installation path without a venv, source checkout or test hook.

The user site initially had no application installation. The test copy used --no-deps --no-cache-dir to preserve already-satisfied dependencies; it was removed afterward. Existing pywin32 311 and other dependencies were unchanged and command resolution returned to the original formal uv tool installation. Fresh dependency resolution was separately tested in the isolated uv tool directory; user-level --no-deps is not claimed as a fresh dependency-resolution test. The formal tool environment was not replaced.

## Automated tests and packaging

**220 passed, 1 skipped**: only another explicitly enabled native task-write test is skipped. No PowerShell exclusion filter is needed. Redundant old-backend contracts were removed and ownership/action checks migrated to Python/native identity API tests; the old 249 count is not directly comparable.

Installed runtime source is checked for absence of powershell.exe/EncodedCommand and for the sole/default Direct COM entry point. Style, lockfile, wheel/sdist module/license/dependency-marker/document checks pass. Lifecycle and canonical-XML regressions remain covered.

Safe local evidence: ignored `.artifacts/auxdisp-codex-quota-install-paths/`, including venv/cli-acceptance.json, uv-tool/cli-acceptance.json and pip-user/cli-acceptance.json, build/test records. No account JSON, tokens or config contents are included.

## Remaining limits

No machine-wide Program Files package install or administrator elevation was performed; system Python with standard user-site installation was tested. Python 3.11/3.12, other architectures and native non-Windows matrices remain unverified. Full terminal closure, logon startup, sleep, crash retries, long-duration operation, manual USB replug and restricted security-policy environments still need acceptance. Removing PowerShell does not guarantee Python/COM permission; report denials and obtain authorization instead of routing around them.

This pre-release acceptance did not modify the formal uv tool installation; the fixes were subsequently included in 0.1.2.
