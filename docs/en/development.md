# Local development

[中文版](../zh/development.md) | [Project overview](README.md)

Each subproject maintains its own `pyproject.toml`, `uv.lock`, and `.venv`. The repository uses no uv Workspace or local source dependencies between distributions. Use the uv version specified by `required-version` in each project's `pyproject.toml`.

## Project identifiers

| Purpose | Display driver library | Codex quota display application |
|---|---|---|
| Project/distribution name | `auxdisp-driver` | `auxdisp-codex-quota` |
| Python import name | `auxdisp_driver` | `auxdisp_codex_quota` |
| CI workflow file | `auxdisp-driver-ci.yml` | `auxdisp-codex-quota-ci.yml` |
| Release workflow file | `auxdisp-driver-release.yml` | `auxdisp-codex-quota-release.yml` |

Use full identifiers in workflow/job names, artifacts, concurrency groups, thread names, and documentation project references, rather than `driver`, `quota`, or `quota-app`. Python modules use underscores. Generic protocol terms, internal variables, device APIs, and screen labels retain names appropriate to their meaning.

## Environments and shared cache

Local development uses one cache at `.artifacts/uv-cache` under the repository root for dependency downloads and builds. Reuse this directory instead of creating additional uv caches for each subproject. Each subproject keeps its own `.venv` to install and isolate its dependencies; virtual environments and the cache remain separate.

```text
auxdisp/
├── .artifacts/uv-cache/
├── packages/auxdisp-driver/.venv/
└── apps/auxdisp-codex-quota/.venv/
```

In PowerShell, first enter the repository root and set an absolute shared cache path:

```powershell
Set-Location 'C:\path\to\auxdisp'
$env:UV_CACHE_DIR = Join-Path $PWD.Path '.artifacts\uv-cache'
```

This variable applies to the current terminal and its child processes, so the cache stays the same when changing subproject directories. Set it again in new terminals, and replace the repository path for other checkout locations. uv creates the cache as needed and creates each project's `.venv` when syncing dependencies.

Run all uv project commands in the relevant subproject directory. For example, for `auxdisp-driver`:

```powershell
Set-Location packages\auxdisp-driver
uv lock --check
uv sync --locked --all-groups
uv run pytest
uv build --no-sources
```

`auxdisp-codex-quota` uses its own directory and lockfile. Check its lock with `uv lock --check --no-sources` and sync with `uv sync --locked --all-groups --no-sources`. Sharing a cache does not create a source dependency between the projects or enable a uv Workspace.

`.artifacts/` and each project's `.venv` are already ignored by Git. Do not commit caches, virtual environments, or build outputs; continue committing `uv.lock`.

If access to `.lock` in the default user cache is denied, first check that `UV_CACHE_DIR` points to the shared directory above. If a Python build subprocess still reports `PermissionError: [WinError 5]` in a temporary directory, check the terminal or execution sandbox's file access permissions. Retry in a local terminal with the appropriate permissions, or follow the authorization process of the managed execution environment. Changing the cache directory alone cannot resolve sandbox permission restrictions; dependency or lockfile changes are unnecessary for this issue.


## auxdisp-codex-quota offline developer tools

The public `preview` command generates one synthetic PNG. Fixtures, error simulation, and bounded PNG rotation live in the source developer tool. Run these commands from `apps/auxdisp-codex-quota` with the shared cache configured above:

```powershell
uv run --locked --no-sources python scripts/dev_display.py --preview ../../.artifacts/auxdisp-codex-quota/single.png --account-index 1
uv run --locked --no-sources python scripts/dev_display.py --preview ../../.artifacts/auxdisp-codex-quota/error.png --simulate-error
uv run --locked --no-sources python scripts/dev_display.py --headless ../../.artifacts/auxdisp-codex-quota/latest.png --duration 2
```

The tool defaults to bundled synthetic data and never invokes codex-auth, USB, or task registration. `--fixture <path>` loads local schema-1 JSON; `--inspect` prints normalized data from that fixture. Custom fixtures can contain identities; do not share raw output. Use `python scripts/dev_display.py --help` for developer options; these options are absent from the installed public CLI. The script is included in the source distribution, rather than the wheel's user entry points.
