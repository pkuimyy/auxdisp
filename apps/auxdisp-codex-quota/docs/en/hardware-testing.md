# auxdisp-codex-quota — Hardware test record

[中文版](../zh/hardware-testing.md) | [Getting started](README.md) | [Background operation](background.md)

## 2026-11-11: foreground run of PyPI 0.1.0

Environment: Windows and Python 3.13.7, with `auxdisp-codex-quota==0.1.0` and `auxdisp-driver==0.1.0` installed from `https://pypi.org/simple`. Modules came from an independent verification environment's `site-packages`; neither package had `direct_url.json` or a local source dependency.

Device: one Turing USB 5.2-inch screen, VID `0x1CBE` / PID `0x0050`, 1280×720 landscape, 30% brightness. An existing local configuration explicitly set the five-hour `NOT LIMITED` policy for one account. Account identities and configuration contents are omitted.

| Check | Result and evidence |
|---|---|
| Installed-package automated tests | All 106 passed, loading the installed package in isolated mode |
| Offline previews | Normal, single-window, and simulated-error 1280×720 PNGs generated successfully; normal preview visually inspected |
| Real account collection | Two read-only collections during a 75-second foreground run, each returning two accounts |
| USB output | Connected successfully; complete frame transfers took approximately 0.274–0.304 seconds, with no transport errors |
| Page rotation | Logs show switches roughly every 15 seconds; user confirmed both accounts rotated correctly |
| Display and policy | User confirmed text, quota display, and correct `NOT LIMITED` behavior |
| Minute clock | An updated frame was sent across the 09:10 minute boundary, Asia/Shanghai time |
| Bounded shutdown | `run --config config.toml --duration 75` completed with exit code 0 |
| Background status query | `status` succeeded; no task or running instance existed before testing |

Local evidence is in the repository's ignored `.artifacts/auxdisp-codex-quota-pypi/` directory: `hardware.log`, `tests.xml`, `result.json`, and three synthetic previews. Real account information is not committed.

## 2026-11-11: pre-release verification of the 0.1.1 ownership fix

The following records verification of the local fix on real Windows / Python 3.13.7, rather than installation acceptance of the final PyPI distribution:

- The existing task passed a read-only query through the fixed bridge; it was neither modified nor deleted.
- All 125 regular automated tests passed, including native Windows SID, local username, qualified username, different-user, unresolved-identity, and marker/action refusal cases.
- One additional opt-in real-task test passed: the program registered a uniquely named temporary task and exercised `start`, `status`, repeated `start`, `stop`, `restart`, and `uninstall-service`. Every ownership check passed; graceful stops did not require forced termination.
- The temporary task used synthetic accounts without calling real codex-auth, with real COM, current-user identity, the Python background entry point, and cross-process IPC. Only the newly created task was removed; the pre-existing task's query result remained unchanged. The background entry point uses normal user diagnostic logs/state and may send synthetic content to a connected screen.

The real-task test is skipped by default. Install the code under test, ensure no display instance is running, then explicitly set `AUXDISP_CODEX_QUOTA_REAL_TASK_TEST=1` in the Windows project directory and run `pytest tests/test_scheduler_ownership.py::test_real_registered_task_lifecycle_preserves_existing_task`. It registers and removes a real temporary task and is not a side-effect-free offline test.

Final regular regression: 125 passed, with the real-task test skipped by default; that test was separately opted into and passed. In the local Python 3.12 attempt, two existing COM checks failed because launching PowerShell subprocesses was denied (WinError 5). Full regression and real-task acceptance therefore used Python 3.13.7; this run does not establish a complete Python 3.12 pass.

## Remaining verification

The PyPI 0.1.0 foreground run above did not register a real task; the subsequent local fix passed temporary-task registration and lifecycle acceptance. Survival after terminal closure, logon startup, sleep/resume, battery behavior, actual crash recovery, long-duration operation, and physical USB unplug/replug recovery with this PyPI version remain unverified. The final distribution still needs verification after the fix is released. Simulated lifecycle tests do not replace system checks.

The user previously confirmed USB unplug/replug recovery and retained historical data during a controlled API TIMEOUT followed by cleared error indicators after recovery on a development build. Those scenarios were not repeated here and are not counted as renewed acceptance of the current distribution. These conclusions cover only this one device and short run.
