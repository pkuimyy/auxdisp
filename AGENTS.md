# Repository instructions

## Monorepo boundaries

- This repository is `auxdisp`; it contains independent projects under
  `packages/` and `apps/`.
- Do not add `[tool.uv.workspace]` or `tool.uv.sources` at the root or in a
  child project.
- Keep a separate `pyproject.toml`, `uv.lock`, and `.venv` in each project.
- For local development, set `UV_CACHE_DIR` to the absolute path of the
  repository's `.artifacts/uv-cache` and reuse it across subprojects. Keep each
  project's `.venv` separate; do not create additional per-project uv caches.
  本地开发共用仓库根目录的 `.artifacts/uv-cache`；各项目保留独立 `.venv`，
  不再创建额外的项目级 uv 缓存目录。详见 `docs/zh/development.md` 和 `docs/en/development.md`。
- Commit each project's `uv.lock`; never commit virtual environments,
  distribution artifacts, or build directories.
- The Codex quota app must depend on a released `auxdisp-driver` package from
  PyPI. Do not use path, editable, workspace, or Git dependencies, and do not
  add the runtime dependency before a compatible driver release exists.
- Do not implement quota business logic before the driver is accepted and
  published.

## Driver source and compatibility

- `packages/auxdisp-driver/` is the only writable home for the extracted
  device drivers. The two upstream checkouts under `D:\project` are read-only.
- Preserve all eight driver families and device-specific behavior. Do not
  rewrite command formats or transport ordering without protocol fixtures that
  prove the change is necessary.
- Do not restore or download the upstream `res/` tree. Keep the extraction
  independent of monitoring, themes, sensors, configuration UI, and scheduler
  code.
- Distinguish code-level checks from physical-device acceptance. Do not mark
  the Turing 5.2-inch hardware matrix passed without a real Windows run.

## Commands and releases

- Run uv commands in the selected project's directory, for example
  `uv lock --check`, `uv sync --locked`, `uv run pytest`, and `uv build
  --no-sources`.
- Keep driver and app CI separate. Official app CI must resolve the driver from
  the package index with `--no-sources`.
- PyPI publishing requires an explicit user-approved release step. Do not push
  Git remotes or publish packages unless explicitly requested.
- Driver publishing uses `.github/workflows/driver-release.yml`, triggered only
  by `auxdisp-driver-v<version>` tags matching the driver's `pyproject.toml`.
  Creating or pushing a release tag requires an explicit release request.
  The workflow uploads the same checked distributions to PyPI and GitHub Release;
  setup and release instructions are in `docs/zh/releases.md` and `docs/en/releases.md`.
- Run each Git command in its own tool call and in the relevant working
  directory. Routine queries, staging, commits, fetch/pull, and normal push are
  allowed; deletion, force push, amend, and history rewriting require explicit
  confirmation.
