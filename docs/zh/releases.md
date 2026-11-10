# 驱动发布

[English version](../en/releases.md) | [本地开发](development.md)

驱动通过 `.github/workflows/driver-release.yml` 发布。只有推送 `auxdisp-driver-v<版本>` tag 才会触发；普通分支推送、PR 和应用 tag 不会上传 PyPI。推送发布 tag 是显式的发布动作，应在版本和实机验收范围确认后进行。

## 首次配置

在 GitHub 仓库 `pkuimyy/auxdisp` 的 Settings → Environments 中创建 `pypi` 环境。若希望推送 tag 后再人工确认一次，可配置 required reviewers；工作流引用环境本身不会自动创建审批规则。

在 PyPI 配置 GitHub Trusted Publisher。尚无首个发行版本时，使用 [Pending Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)：

| 字段 | 值 |
|---|---|
| PyPI 项目名 | `auxdisp-driver` |
| GitHub owner | `pkuimyy` |
| Repository | `auxdisp` |
| Workflow filename | `driver-release.yml` |
| Environment | `pypi` |

已有 PyPI 项目时，在该项目的 Publishing 设置中添加相同配置。工作流使用 OIDC，无需保存 PyPI API token。配置方式见 [PyPI Trusted Publishing 文档](https://docs.pypi.org/trusted-publishers/using-a-publisher/)。这些账号和环境配置不由本地 YAML 文件代替，需要管理员在相应服务中完成。

## 版本与 tag

先更新 `packages/auxdisp-driver/pyproject.toml` 的版本、驱动独立的 `uv.lock` 和中英文变更记录，再提交代码。tag 必须与元数据逐字匹配：

| 包版本 | 发布 tag | GitHub Release |
|---|---|---|
| `0.1.0` | `auxdisp-driver-v0.1.0` | 普通发布 |
| `0.1.0a1` | `auxdisp-driver-v0.1.0a1` | 预发布 |
| `0.1.0b1` | `auxdisp-driver-v0.1.0b1` | 预发布 |
| `0.1.0rc1` | `auxdisp-driver-v0.1.0rc1` | 预发布 |

目前支持三段数字版本，以及 `aN`、`bN`、`rcN` 后缀。裸 `v0.1.0`、本地版本、开发版本或版本不匹配的 tag 不会发布。更新锁文件时在驱动目录运行 `uv lock`，本地检查 tag 可运行 `uv run python scripts/check_release.py auxdisp-driver-v0.1.0`。

以下仅为决定发布 `0.1.0` 后执行的示例；配置工作流不等于已经发布。在仓库根目录运行：

```powershell
git push origin main
git tag -a auxdisp-driver-v0.1.0 -m "auxdisp-driver 0.1.0"
git push origin auxdisp-driver-v0.1.0
```

若选择预发布，先修改包版本，再替换示例中的 tag。不要通过移动、删除或强制覆盖已发布 tag 修复发行版；修正代码后使用新版本。

## 流水线行为

1. Windows / Python 3.13：校验 tag 与包名、版本，按锁文件安装依赖，执行 Ruff 和测试。
2. 构建 wheel 和源码包，检查许可证、文档链接及 Twine 严格格式校验，并在独立环境安装 wheel。
3. 将这两份文件保存为 Actions artifact `auxdisp-driver-distributions`，保留 14 天。
4. Linux 发布任务在 `pypi` 环境中，通过 Trusted Publishing 上传同一份文件。
5. PyPI 上传成功后，创建对应的 GitHub Release，并附上同一份 wheel 和源码压缩包。`a`、`b`、`rc` 版本标记为 GitHub 预发布；普通版本不作此标记。

构建任务只有仓库读取权限，PyPI 任务只有 OIDC 权限，GitHub Release 任务拥有发布制品所需的 `contents: write`。两个发布任务都不会重新构建文件，应用占位项目不参与此发布流程。

PyPI 与 GitHub 无法原子发布：若 PyPI 已成功而 GitHub Release 失败，应在 artifact 仍保留时只重跑失败任务，复用该次构建产物。若失败的创建操作遗留 draft Release，先检查其资产再完成发布，不要盲目覆盖。若 PyPI 部分文件已上传，先核对该版本现存文件与本次 artifact，再决定恢复方式；工作流不会静默跳过重复文件。已上传的版本不可用重新打包的文件覆盖。

自动化测试不会代替实机验收。发行说明应明确已验证的设备和功能，不能将单块屏幕的测试结果扩大为所有型号通过。
