# Repository instructions

## Project identifiers

- Use the canonical project/distribution identifiers `auxdisp-driver` and
  `auxdisp-codex-quota` in workflow filenames, workflow/job names, artifacts,
  concurrency groups, thread names, and documentation titles or project references.
  Do not use `driver`, `quota`, or `quota-app` as shortened project identifiers.
- Python imports use the corresponding valid module names `auxdisp_driver` and
  `auxdisp_codex_quota`. Keep generic protocol terms, internal variable names,
  device APIs, and descriptive screen labels appropriate to their meaning.

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
- `auxdisp-codex-quota` must depend on a released `auxdisp-driver` package from
  PyPI. Do not use path, editable, workspace, or Git dependencies, and do not
  add the runtime dependency before a compatible driver release exists.
- Do not implement `auxdisp-codex-quota` business logic before `auxdisp-driver`
  is accepted and published.

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

## Documentation scope / 文档范围

- Keep README files focused on prospective users: purpose, installation, quick
  start, supported devices, and material limitations. Keep `docs/zh` and
  `docs/en` for durable usage, configuration, troubleshooting, architecture,
  development, and release instructions; update existing pages before adding one.
  README 面向潜在用户；正式 docs 只保留长期有效的使用与维护指南，优先更新已有页面。
- Store plans, investigations, migration histories, local environment incidents,
  test/acceptance reports, command transcripts, and release verification evidence
  under the ignored root `.codex/` directory. Store generated logs, screenshots,
  and distributions under `.artifacts/`. Do not commit or package these records.
  计划、排查、迁移与验收过程记录归档到 `.codex/`；生成制品放在 `.artifacts/`。
- Public documentation must not link to `.codex/`, `.artifacts/`, or local-only
  records. Extract only user-actionable instructions and concise compatibility
  limits from such records. Do not publish machine-specific paths, identities,
  security-product details, raw logs, test counts, or session chronology.
  正式文档不引用本地记录，不披露本机身份、环境细节、日志或测试流水账。
- Keep Chinese and English guidance aligned. Maintain one home for each topic,
  link to it instead of duplicating details, and remove stale navigation when
  archiving pages. Changelogs describe released behavior, not validation sessions.
  中英文同步；同一主题集中维护；归档时清理链接；更新日志只描述发行变化。
- Preserve license/source attribution, API contracts, security-relevant behavior,
  and honest support limits. Local hardware results must not become unsupported
  compatibility claims. Validate documentation links and package contents after
  restructuring; documentation-only work must not manipulate real tasks/devices.
  保留许可证、来源说明、接口约定和真实支持边界；文档整理后检查链接与包内容。

## Commands and releases

- Run uv commands in the selected project's directory, for example
  `uv lock --check`, `uv sync --locked`, `uv run pytest`, and `uv build
  --no-sources`.
- Keep `auxdisp-driver` and `auxdisp-codex-quota` CI separate. Official
  `auxdisp-codex-quota` CI must resolve `auxdisp-driver` from
  the package index with `--no-sources`.
- PyPI publishing requires an explicit user-approved release step. Do not push
  Git remotes or publish packages unless explicitly requested.
- `auxdisp-driver` publishing uses
  `.github/workflows/auxdisp-driver-release.yml`, triggered only by
  `auxdisp-driver-v<version>` tags matching the project's `pyproject.toml`.
  Creating or pushing a release tag requires an explicit release request.
  The workflow uploads the same checked distributions to PyPI and GitHub Release;
  setup and release instructions are in `docs/zh/releases.md` and `docs/en/releases.md`.
- `auxdisp-codex-quota` publishing uses
  `.github/workflows/auxdisp-codex-quota-release.yml`, triggered only by matching
  `auxdisp-codex-quota-v<version>` tags. It independently tests and builds the app,
  resolves `auxdisp-driver` from PyPI, and publishes the same checked distributions
  to PyPI and GitHub Release. Release instructions are in the app's bilingual
  `docs/zh/releases.md` and `docs/en/releases.md`; tags require an explicit release request.
- Run each Git command in its own tool call and in the relevant working
  directory. Routine queries, staging, commits, fetch/pull, and normal push are
  allowed; deletion, force push, amend, and history rewriting require explicit
  confirmation.
