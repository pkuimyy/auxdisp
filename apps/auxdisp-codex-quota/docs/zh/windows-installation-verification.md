# auxdisp-codex-quota — Direct COM 与正式安装路径验证

[English](../en/windows-installation-verification.md) | [后台管理](background.md) | [生命周期历史](windows-lifecycle-hardening.md)

日期：2026-11-11，北京时间。本报告记录 0.1.2 发布前验证；当时测试 wheel 暂沿用 0.1.1 元数据，不能视为 PyPI 0.1.1 已包含修复。

## 最终实现

- 完全移除应用运行时 PowerShell Bridge、EncodedCommand 和替代后端；默认及唯一后端为 Python Direct COM。
- `scheduler.py` 仅为兼容入口，`TaskScheduler` 指向 `DirectComTaskScheduler`；保留 TaskSpec/NS/管理标记导出，不保留旧实现。
- 保持 SID 规范化、管理标记、单一动作、启动参数校验及旧 `-I -m` 任务识别；通过 `start` / `restart` 更新参数，不要求删除合法旧任务。
- Python worker 仍有超时和取消边界；超时不代表服务端写入已撤销。权限拒绝时明确报错，不换路径重试。
- Windows 依赖为 `pywin32>=311`，其他平台不安装；实际覆盖现有用户环境的 311 和独立环境的 312。

CI 的 PowerShell shell、文档中的 PowerShell 命令块和 codex-auth npm 包的 `.ps1` 文件名识别不是运行时后端。采集器仍解析并直接调用原生 exe，不执行该脚本。

## 验证方法

使用构建 wheel 的真实 `.exe` CLI，不给 CLI 注入后端或替换 ServiceController。每轮从源码项目之外的目录执行：

1. 确认默认当前用户任务不存在，且没有运行实例；已有任务或实例会导致测试拒绝开始。
2. 显式提供合成账户配置，临时创建可读测试采集文件，不调用真实 codex-auth。
3. 调用 `start`、`status`、重复 `start`、`stop`、`restart`、`uninstall-service`；核对任务、实例和健康记录。
4. 确认 CLI 进程退出后后台仍运行，重复 start 不改变 host instance。
5. 删除本轮创建的默认任务及临时采集文件，确认无实例残留；恢复原 service/launch/last-stop 状态文件，核对默认 config.toml 未变。

脚本为 `scripts/validate_installed_cli.py`，必须显式传入 `--allow-default-task-test`。这是有任务写入和短暂合成屏幕输出的授权验收，不属于默认自动化测试。正式 CLI 固定使用当前用户任务名，因此本轮在确认该名称原本不存在后创建、清理；没有覆盖已有任务。诊断日志会追加测试记录。

## 安装矩阵结果

环境：Windows、系统 CPython 3.13.7 x64、已连接的 Turing USB 5.2 英寸屏幕。

| 安装形态 | 实际安装与入口 | pywin32 | 结果 |
|---|---|---|---|
| wheel / venv | wheel 安装至项目 `.venv-wheel`，直接运行 Scripts 中的 CLI | 312 | 全部通过 |
| uv tool | 独立 UV_TOOL_DIR/UV_TOOL_BIN_DIR 安装同一 wheel，直接运行生成的 CLI | 312 | 全部通过 |
| 标准 `pip --user` | 系统 Python 将 wheel 安装到真实用户 site-packages，运行用户 Scripts 下的 CLI | 311 | 全部通过 |

三轮均确认：进程正常、健康记录新鲜、phase=running、重复启动单实例、正常停止/重启、卸载任务成功、无实例残留、默认配置不变、原诊断状态恢复。pip 用户级的计划任务实际由系统 `pythonw.exe` 加载用户 site-packages；不依赖 venv、测试钩子或源码目录，已覆盖此前的真实失败安装模式。

用户环境原先没有安装本应用；只临时安装测试副本，使用 `--no-deps --no-cache-dir` 保留已经满足要求的依赖。验证后已卸载本次用户副本，原有 pywin32 311 和其他依赖未变，PATH 命令解析恢复到原先 uv tool 安装。uv tool 依赖解析/安装另在全新隔离工具目录完成；不把用户级 `--no-deps` 安装当成全新依赖解析测试。正式 uv tool 环境未覆盖。

## 自动化与制品

完整自动化：**220 passed、1 skipped**。只跳过需显式启用的另一组实机任务写入测试；不再为 PowerShell 排除测试。旧后端重复合约被移除，SID/参数拒绝等规则转为 Python/native 身份 API 测试；与此前 249 数量不可直接比较。

新增安装包源代码检查确认不存在运行时 `powershell.exe` 或 `EncodedCommand`，并确认默认类与兼容入口均为 Direct COM。编译风格、锁文件、wheel/sdist 模块/许可证/依赖标记/文档检查通过。生命周期与 XML 默认值回归保留。

本地证据在忽略目录 `.artifacts/auxdisp-codex-quota-install-paths/`：`venv/cli-acceptance.json`、`uv-tool/cli-acceptance.json`、`pip-user/cli-acceptance.json`，以及构建和自动化记录。报告只保存安全状态元数据，不包含账户 JSON、Token 或配置内容。

## 边界

- 未向系统 Program Files 的全局 site-packages 安装，不为测试请求管理员权限；已验证系统 Python + 标准用户安装。
- 未完成 Python 3.11/3.12、其他架构或原生非 Windows 安装矩阵。
- 完整关闭终端、登录自启、休眠、崩溃重试、长期运行、USB 人工拔插及受限安全策略环境仍需验收。
- 移除 PowerShell 不保证所有安全软件允许 Python/COM；访问拒绝仍需核查权限或管理员授权，应用不绕行。
- 本次预发布验证没有改变正式 uv tool 安装；相关修复随后纳入 0.1.2。
