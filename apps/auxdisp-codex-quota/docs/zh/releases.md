# auxdisp-codex-quota — 发布

[English version](../en/releases.md) | [后台安装与运行](background.md)

发布工作流为 `.github/workflows/auxdisp-codex-quota-release.yml`，仅由 `auxdisp-codex-quota-v<版本>` tag 触发。包名和 tag 版本必须与 `pyproject.toml` 完全一致；`aN`、`bN`、`rcN` 版本标记为 GitHub 预发布。分支推送和 `auxdisp-driver` tag 不发布本应用。

## Trusted Publisher

| 字段 | 值 |
|---|---|
| PyPI 项目 | `auxdisp-codex-quota` |
| GitHub owner | `pkuimyy` |
| Repository | `auxdisp` |
| Workflow filename | `auxdisp-codex-quota-release.yml` |
| Environment | `pypi` |

首次发布前配置 PyPI Pending Publisher；项目已存在时配置其 Trusted Publisher。GitHub 的 `pypi` 环境需要允许 `auxdisp-codex-quota-v*` tag。工作流通过 OIDC 发布，不保存 PyPI API token。

## 发布流程

1. Windows/Python 3.13 按锁文件从包索引安装依赖，校验 tag、执行 Ruff 和测试。
2. 构建 wheel/sdist，校验模块、许可证、PyPI README 与文档链接，并通过 Twine strict 检查。
3. 独立安装 wheel，确认 `auxdisp-driver` 来自 PyPI，并以合成数据验证预览和有界前台运行。
4. 保存 `auxdisp-codex-quota-distributions` artifact；Linux 发布任务将这份制品上传 PyPI。
5. PyPI 成功后创建 GitHub Release，附上同一次构建的 wheel 和源码包。

只能在用户明确授权发布后创建和推送 tag。以下是发布 0.1.0 的命令示例，在仓库根目录执行：

```powershell
git push origin main
git tag -a auxdisp-codex-quota-v0.1.0 -m "auxdisp-codex-quota 0.1.0"
git push origin auxdisp-codex-quota-v0.1.0
```

若 PyPI 已成功但 GitHub Release 失败，仅重跑失败任务，复用保留 14 天的同一份制品，不重新打包或覆盖已发布文件。发布失败不通过移动或删除原 tag 修复；需要代码修正时使用新版本。
