# 本地开发

[English version](../en/development.md) | [项目介绍](README.md)

每个子项目独立维护 `pyproject.toml`、`uv.lock` 和 `.venv`。仓库不使用 uv Workspace，也不建立发行包之间的本地源码依赖。uv 版本以各项目 `pyproject.toml` 中的 `required-version` 为准。

## 项目标识

| 用途 | 显示驱动库 | Codex 用量显示应用 |
|---|---|---|
| 项目名、发行包名 | `auxdisp-driver` | `auxdisp-codex-quota` |
| Python 导入名 | `auxdisp_driver` | `auxdisp_codex_quota` |
| CI 工作流文件 | `auxdisp-driver-ci.yml` | `auxdisp-codex-quota-ci.yml` |
| 发布工作流文件 | `auxdisp-driver-release.yml` | `auxdisp-codex-quota-release.yml` |

工作流名称、任务显示名称、artifact、并发组、线程名称和文档中的项目标识使用完整名称，不使用 `driver`、`quota` 或 `quota-app` 简写。Python 模块名使用下划线；协议术语、内部变量、设备 API 和屏幕标签按其实际含义命名。

## 环境与共享缓存

本地开发统一使用仓库根目录下的 `.artifacts/uv-cache`，共享依赖下载与构建缓存，避免为每个子项目创建额外的 uv 缓存目录。各子项目仍保留独立的 `.venv`，用于安装和隔离各自的依赖；虚拟环境与缓存分开存放。

```text
auxdisp/
├── .artifacts/uv-cache/
├── packages/auxdisp-driver/.venv/
└── apps/auxdisp-codex-quota/.venv/
```

在 PowerShell 中，先进入仓库根目录并设置共享缓存的绝对路径：

```powershell
Set-Location 'C:\path\to\auxdisp'
$env:UV_CACHE_DIR = Join-Path $PWD.Path '.artifacts\uv-cache'
```

该变量对当前终端及其子进程生效，切换子项目目录后仍使用同一缓存；新终端需重新设置。其它检出位置请替换仓库路径。uv 会在需要时创建缓存目录，并在同步依赖时创建各项目的 `.venv`。

所有 uv 项目命令都在对应子项目目录执行。例如，`auxdisp-driver`：

```powershell
Set-Location packages\auxdisp-driver
uv lock --check
uv sync --locked --all-groups
uv run pytest
uv build --no-sources
```

`auxdisp-codex-quota` 使用自己的目录与锁文件；检查锁文件和同步依赖时分别使用 `uv lock --check --no-sources` 和 `uv sync --locked --all-groups --no-sources`。共享缓存不会建立两个项目之间的源码依赖，也不会启用 uv Workspace。

`.artifacts/` 和各项目的 `.venv` 已被 Git 忽略；缓存、虚拟环境和构建产物不提交，`uv.lock` 继续提交。

若默认用户缓存目录出现 `.lock` 拒绝访问，先检查 `UV_CACHE_DIR` 是否已指向上述共享目录。若 Python 构建子进程仍在临时目录中报 `PermissionError: [WinError 5]`，应检查终端或执行沙箱的文件访问权限；在具备相应权限的本地终端重试，受控执行环境则按其授权流程处理。更换缓存目录不能单独解决沙箱权限问题，无需为此更改依赖或锁文件。


## auxdisp-codex-quota 离线开发工具

用户入口只保留 `preview` 生成单张合成图片；fixture、错误模拟和有界 PNG 轮播在源码开发工具中提供。以下命令在 `apps/auxdisp-codex-quota` 目录执行，并使用上文配置的共享缓存：

```powershell
uv run --locked --no-sources python scripts/dev_display.py --preview ../../.artifacts/auxdisp-codex-quota/single.png --account-index 1
uv run --locked --no-sources python scripts/dev_display.py --preview ../../.artifacts/auxdisp-codex-quota/error.png --simulate-error
uv run --locked --no-sources python scripts/dev_display.py --headless ../../.artifacts/auxdisp-codex-quota/latest.png --duration 2
```

开发工具默认使用包内合成数据，始终不调用 codex-auth 或 USB，也不注册任务。`--fixture <路径>` 可以替换为 schema 1 的本地 JSON；`--inspect` 查看这份 fixture 的规范化数据。自定义 fixture 可能包含账户信息，勿公开原始输出。开发选项通过 `python scripts/dev_display.py --help` 查看；它们不出现在安装后的公开 CLI 中。开发脚本随源码包提供，不放入 wheel 的用户入口。
