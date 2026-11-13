# auxdisp-codex-quota — 故障排查

[English](../en/troubleshooting.md) | [应用入门](https://github.com/pkuimyy/auxdisp/blob/main/apps/auxdisp-codex-quota/README.md) | [后台管理](background.md)

## 安装后找不到 CLI

```powershell
python -m pip show auxdisp-codex-quota
python -m auxdisp_codex_quota --help
Get-Command auxdisp-codex-quota -All
```

确认 `python` 和安装时的 `pip` 属于同一环境。模块命令可运行但 CLI 不可用时，将该环境的 Scripts 目录加入 PATH，或激活对应虚拟环境。之后可用 `python -m auxdisp_codex_quota start` 等模块形式运行。虚拟环境被删除时需要在保留的环境重装并 `start` 更新任务。

## 找不到 codex-auth 或没有账户

```powershell
Get-Command codex-auth -All
codex-auth list --api --json
```

在运行应用的同一 Windows 用户下，按 [codex-auth](https://github.com/Loongphy/codex-auth) 说明安装并配置账户。命令输出含身份信息，不要公开。应用显示 `COMMAND_NOT_FOUND` 时检查 PATH；`CONFIGURE_NATIVE_CODEX_AUTH_EXE` 表示需在配置中指定原生 exe 的完整路径。配置示例见 [配置指南](usage.md)，修改后 `restart`。

## USB 无法识别

核对 Turing USB 5.2 英寸、VID `0x1CBE` / PID `0x0050` 和数据线；同品牌其他型号不属于应用支持范围。用 Windows 设备管理器检查设备和兼容接口驱动。`libusb-package` 是用户态库，安装成功不代表 Windows 接口驱动或访问权限已正确配置。不要仅凭 `process_running=true` 判断 USB 可用。

更多设备信息见 [支持设备](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md)。

## 连接正常但没有画面

```powershell
auxdisp-codex-quota status
Get-Content "$env:LOCALAPPDATA\auxdisp-codex-quota\logs\service.log" -Tail 50
auxdisp-codex-quota stop
auxdisp-codex-quota run
```

检查亮度是否为 0、是否使用横屏、是否有 USB unavailable / transfer failed 日志。`usb_connected` 是最近传输观察值；`null` 表示未知、未运行或健康心跳过期，不代表连接成功。前台 `run` 会使用真实账户和 USB，Ctrl+C 退出；与后台共享单实例锁，因此先停止后台。先尝试 `preview --output preview.png` 可单独检查渲染。USB 断开会自动重试最新一帧。

## API ERROR / STALE

先在当前用户下执行 `codex-auth list --api --json`，在本地检查刷新状态、网络和授权是否可用。应用不会自动登录、切换账户或使用重置卡。命令超时、退出失败、未知 schema 或单账户刷新失败都会提示错误；有历史数据时继续显示并标记 STALE，历史不跨重启保存。不要把 API OK 理解为每个周期都有数据，也不要把 LAST OK 当成源数据更新时间。

## UNAVAILABLE / DATA UNAVAILABLE

这表示没有该周期的可用数据，不等于额度耗尽。5 小时 / 7 天按 300 / 10080 分钟识别；某账户可能只返回 7 天窗口，即使它位于 primary。只有明确知道账户无相应限制时才设置 `unlimited_windows`，不要为了隐藏缺失数据而配置无限额度。

## Windows 后台启动失败或停止后又启动

根据错误码区分进程创建、超时、响应解析和 COM 调用失败。通用错误不能直接证明安全软件拦截；请结合任务计划程序和系统事件检查权限及策略。

若错误包含 `rollback=failed/unavailable` 或最终状态未知，不代表任务已经清理。先检查 `status` 和任务计划程序中的实际状态，再决定恢复操作。

检查 `status` 的 `registered`、`enabled` 和 `process_running`。注册失败时检查 Task Scheduler 是否可用、当前用户任务权限及系统策略；应用不自动提权。确认任务使用的 Python 环境仍存在且具备 `pythonw.exe`，以及 codex-auth 路径可解析。升级或迁移安装后运行 `start` 更新关联。

正常停止请用 `auxdisp-codex-quota stop`，它会先禁用登录启动和崩溃重试；仅关闭终端或手动终止进程不同于 stop。`restart` 会重新启用并启动。需要移除任务请用 `uninstall-service`，再卸载包。诊断和超时停止行为见 [后台运行](background.md).

## 用户级 pip 安装后后台进程立即退出

0.1.1 及更早版本的后台 `-I` 参数禁用用户级 `site-packages`，因此 CLI 可用但后台找不到模块，甚至来不及创建新日志。可用 `python -m pip show auxdisp-codex-quota` 查看安装位置。0.1.2 已改用 `-E -P` 修复；旧发行版请使用虚拟环境或 uv 工具环境。无需重装 Python。安装包含修复的版本后运行 `start` / `restart` 更新现有任务。详见 [后台运行](background.md)。

## 任务所有权错误

从 0.1.1 起，程序将 Task Scheduler 的 `Principal.UserId`（SID、本地用户名或 `DOMAIN\username`）通过 Windows 身份 API 规范化为 SID，再与当前用户 SID 比较。不会仅凭同名任务或合法 Description 接管任务。旧版 `TASK_OWNERSHIP_MISMATCH` 可能由同一用户的用户名/SID 表示差异触发；修复不需要删除已有任务。

| 错误 | 含义 |
|---|---|
| `TASK_IDENTITY_UNRESOLVED` | Windows 无法解析任务身份，或身份为空/无效；拒绝管理 |
| `TASK_IDENTITY_MISMATCH` | 解析出的 SID 属于其他用户；拒绝管理 |
| `TASK_MARKER_MISMATCH` | Description 不包含预期管理标记；拒绝管理 |
| `TASK_ACTION_MISMATCH` | 动作不是唯一的预期后台启动动作；拒绝管理 |

在任务计划程序中只读检查任务身份、Description 和启动参数；不要通过删除任务或绕过检查来掩盖问题。使用包含修复的安装版本后重试；仍失败时附脱敏错误码。

## 提交问题

请附操作系统、Python 和两个包的版本、设备 VID/PID、执行命令、脱敏的 status 与日志。不要提交真实邮箱、账户名、account_key、认证文件、原始 codex-auth JSON 或未脱敏截图。 [GitHub Issues](https://github.com/pkuimyy/auxdisp/issues).
