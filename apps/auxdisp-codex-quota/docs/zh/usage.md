# auxdisp-codex-quota — 配置与预览

[English](../en/usage.md) | [应用入门](https://github.com/pkuimyy/auxdisp/blob/main/apps/auxdisp-codex-quota/README.md) | [后台管理](background.md)

## 配置位置

优先级：显式 `--config <路径>` → `%LOCALAPPDATA%\auxdisp-codex-quota\config.toml` → 内置默认值。不自动读取工作目录。首次 `start` 会创建仅含注释的默认文件，不覆盖已有配置。

```powershell
notepad "$env:LOCALAPPDATA\auxdisp-codex-quota\config.toml"
auxdisp-codex-quota restart
```

默认文件尚未创建时，可先在该用户数据目录创建文件夹和 `config.toml`，或直接创建其他位置的 TOML 文件并显式指定：

```powershell
auxdisp-codex-quota start --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota restart --config C:\Users\Me\auxdisp-config.toml
```

## 设置与默认值

| 设置 | 默认值 |
|---|---|
| `collector.executable` | `codex-auth` |
| `collector.refresh_seconds` | 60 s |
| `collector.timeout_seconds` | 20 s |
| `rotation.seconds` | 15 s |
| `display.orientation` | `landscape` (1280×720) |
| `display.brightness` | 30% |
| `display.reconnect_seconds` | 5 s |
| `render.thresholds` | `[75, 50, 25]` |
| `render.font` | 空字符串，使用系统字体 |
| `logging.level` | `INFO` |

以下可直接作为配置起点；未列出的设置使用默认值。亮度必须为 0–100 的整数，时间间隔必须为正数；方向仅接受 `landscape`。

```toml
[collector]
executable = "codex-auth"
refresh_seconds = 60
timeout_seconds = 20

[rotation]
seconds = 15

[display]
brightness = 30
reconnect_seconds = 5

[render]
font = ""
thresholds = [75, 50, 25]
```

Windows 原生路径可使用 TOML 单引号，避免反斜杠转义：

```toml
[collector]
executable = 'C:\Tools\codex-auth.exe'

[render]
font = 'C:\Windows\Fonts\consola.ttf'
```

这段是另一份示例：将字段合并到已有表，勿在同一文件重复定义 `[collector]` 或 `[render]`。字号由代码固定：名称与百分比 44px，其他信息 24px；字体路径只改变字体。默认等宽字体，中文有系统字体回退；长文本在预留区域省略。

## 特殊账户额度策略

直接从数据源只读查看稳定 `account_key`：

```powershell
codex-auth list --api --json
```

输出包含账户身份信息，不要公开。如果你有明确依据确认某账户没有 5 小时限制，才按完整稳定 ID 配置：

```toml
[accounts."replace-with-exact-stable-account-key"]
unlimited_windows = [300]
```

策略只匹配稳定 ID，支持 300 / 10080 分钟。不会从邮箱后缀、`secondary=null` 或缺失窗口推断无限额度。没有数据默认显示 `DATA UNAVAILABLE`，不是 0%。

## PNG 预览

```powershell
auxdisp-codex-quota preview
auxdisp-codex-quota preview --output .\images\preview.png
auxdisp-codex-quota preview --config .\settings.toml
```

`preview` 只用包内合成账户生成 1280×720 PNG，不调用 codex-auth、USB 或后台任务，也不打开浏览器。默认选择首个合成账户与第一张卡片页，时钟和倒计时使用生成时刻。

默认输出到命令执行时当前目录中的 `auxdisp-codex-quota-preview.png`；`--output` 可指定相对或绝对文件路径，必要时创建父目录。同名文件会被替换；写入失败返回非零退出码，并保留原文件。完成后输出模拟数据说明和文件绝对路径。

`--config` 使用指定配置中的渲染设置；未指定时遵循用户配置文件和内置默认值的优先级。预览不受配置中的采集命令、亮度或 USB 设置影响。测试 fixture、错误模拟和持续 PNG 输出属于开发工具，见[本地开发](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)。

## 数据来源与边界

仅执行 `codex-auth list --api --json` ([JSON API schema 1](https://github.com/Loongphy/codex-auth/blob/main/docs/json-api.md))。Windows 官方 npm 包可自动解析原生 exe（含嵌套/扁平布局）；其他安装可显式配置原生路径。

周期按分钟数匹配，不依赖 primary/secondary 顺序。API ERROR 可能来自整个命令或当前账户刷新失败；历史只保存在当前运行进程的内存中，重新启动不会恢复额度快照。LAST OK 是整体请求成功时间，不是每个账户的 `usage.updated_at`。

额度表的 `RESET AT` 显示本机时区的重置日期与时间，`RESET IN` 显示剩余时长；到达重置时间后显示 `DUE`，等待下一次采集确认实际额度。10 格条按剩余值向上取整；剩余百分比最多两位小数。

屏幕不显示 `CREDITS`。`RESET CARDS` 读取 `usage.reset_credits`，有效的零值显示 `0`，缺失或无效值显示 `N/A`，不根据卡片明细推测数量。

卡片明细读取 `usage.reset_credit`，保留每张卡的名称、状态、到期日期时间（`EXPIRES AT`）和剩余时长（`EXPIRES IN`）。按到期时间从近到远排序，缺少有效到期时间的卡放在最后并显示 `--`；已过期显示 `EXPIRED`。每页最多三张，多页会在一个账户轮播周期内自动轮换；右侧用 `RESET CARDS PAGES 1/1` 标识卡片页码，底部用 `ACCOUNT 1/3` 标识账户序号与总数。卡片翻页只改变卡片区，不切换账户或改变上方额度条；账户仍按配置的轮播周期切换，额度采集和倒计时独立更新。没有明细时显示 `NO CARD DETAILS` 或 `N/A`，不代表卡片数量为零。

剩余时长使用天／小时或小时／分钟，最后不足一分钟显示 `1m`。倒计时随画面更新，不会自动使用卡片。刷新失败时保留历史额度和卡片并标记 `STALE`，成功刷新后替换历史数据。

开发环境、测试和独立构建请见 [本地开发](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)；异常检查见 [排障](troubleshooting.md).
