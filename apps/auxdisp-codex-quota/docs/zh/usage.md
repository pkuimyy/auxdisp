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

只读查看规范化数据与稳定 `account_key`：

```powershell
auxdisp-codex-quota --inspect
```

输出包含账户身份信息，不要公开。如果你有明确依据确认某账户没有 5 小时限制，才按完整稳定 ID 配置：

```toml
[accounts."replace-with-exact-stable-account-key"]
unlimited_windows = [300]
```

策略只匹配稳定 ID，支持 300 / 10080 分钟。不会从邮箱后缀、`secondary=null` 或缺失窗口推断无限额度。没有数据默认显示 `DATA UNAVAILABLE`，不是 0%。

## 离线与无设备运行

```powershell
auxdisp-codex-quota --preview dual.png
auxdisp-codex-quota --preview weekly.png --account-index 1
auxdisp-codex-quota --preview error.png --simulate-error
auxdisp-codex-quota run --demo --headless latest.png --duration 60
```

这些命令使用合成账户，不访问真实账户或 USB。`--account-index` 从 0 起算。`--fixture <JSON路径>` 可使用符合 schema 1 的自定义数据。

```powershell
auxdisp-codex-quota run --headless real-accounts.png --duration 65
```

**这个命令会读取真实账户**，只把 USB 输出替换为 PNG；图片可能包含账户名称或邮箱，发布前请脱敏。与 `--demo` 组合才完全离线。`--duration` 到期自动退出；未指定时持续运行至 Ctrl+C。

## 数据来源与边界

仅执行 `codex-auth list --api --json` ([JSON API schema 1](https://github.com/Loongphy/codex-auth/blob/main/docs/json-api.md))。Windows 官方 npm 包可自动解析原生 exe（含嵌套/扁平布局）；其他安装可显式配置原生路径。

周期按分钟数匹配，不依赖 primary/secondary 顺序。API ERROR 可能来自整个命令或当前账户刷新失败；历史只保存在当前运行进程的内存中，重新启动不会恢复额度快照。LAST OK 是整体请求成功时间，不是每个账户的 `usage.updated_at`。

CREDITS / RESET CARDS / NEXT EXPIRY 固定为 `N/A`，尚未接入数据。10 格条按剩余值向上取整；剩余百分比最多两位小数。

开发环境、测试和独立构建请见 [本地开发](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)；异常检查见 [排障](troubleshooting.md).
