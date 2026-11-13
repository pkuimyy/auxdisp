# auxdisp-codex-quota — Windows 后台运行

[English version](../en/background.md) | [配置与预览](usage.md)

## 安装与启动

发行包安装后的用户接口如下。请先独立安装并配置当前 Windows 用户的 `codex-auth`，准备可访问的 Turing USB 5.2 英寸设备。

```powershell
pip install auxdisp-codex-quota
auxdisp-codex-quota start
auxdisp-codex-quota status
auxdisp-codex-quota stop
auxdisp-codex-quota restart
```

`pip install` 只安装包和 CLI，不注册任务。第一次 `start` 才注册 `auxdisp-codex-quota-<当前用户 SID>` 计划任务，并立即启动。应用使用当前安装环境的绝对 `pythonw.exe` 路径调用包内入口；无需源码目录、uv 缓存或打开的 PowerShell 窗口。

从 0.1.2 起使用 Python Direct COM 管理计划任务，支持标准 `pip --user`、venv 和 uv tool 安装。Windows 会安装 pywin32；权限拒绝时返回错误。

0.1.2 后台使用 `-E -P -m auxdisp_codex_quota._background`：忽略解释器环境变量（例如 `PYTHONPATH`），不将当前目录加入模块搜索路径，同时允许标准用户级 `site-packages`，供应用和依赖加载。用户目录仍属于受信任的 Python 安装环境，包括其中的 `.pth` 和定制模块；这不是完整的 `-I` 隔离模式。支持全局、标准 `pip --user` 和虚拟环境安装；仍需保留所用 Python 环境。

0.1.1 及更早版本使用 `-I`，会隐藏用户级包目录；这些发行版的后台运行请使用虚拟环境或 uv 工具环境。安装包含修复的版本后执行 `start` 或 `restart`，原任务会更新启动参数，无需删除任务；旧参数格式仍接受完整所有权校验。

任务仅在当前用户登录时运行，登录后自动启动，使用普通用户权限，不要求管理员权限，也不会尝试提权。若 Windows 策略拒绝注册，命令返回错误，应由用户或管理员检查相应策略。

已运行时再次 `start` 不创建第二个实例。`start` 会核对包版本、任务关联的解释器与启动参数；升级包版本或迁移到另一 Python 安装环境时，先正常停止旧实例，再更新同一个任务。修改配置后使用 `restart`；显式配置路径请在 `start` 或 `restart` 时提供，例如：

```powershell
auxdisp-codex-quota start --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota restart --config C:\Users\Me\auxdisp-config.toml
```

## 更新包

在原安装环境中执行，保留已有配置：

```powershell
auxdisp-codex-quota stop
pip install --upgrade auxdisp-codex-quota
auxdisp-codex-quota start
```

升级本身不会重启进程；如果已经在运行中升级，执行 `restart`。修改配置也需要 `restart`。使用自定义文件时，在最后的 `start` 或 `restart` 重复提供 `--config`。排障见 [故障排查](troubleshooting.md).

## 配置、日志与状态

```text
%LOCALAPPDATA%\auxdisp-codex-quota\
├── config.toml
├── logs\service.log
└── state\
    ├── service.json
    ├── launch.json
    └── last-stop.json
```

配置优先级为显式 `--config`、当前用户数据目录的 `config.toml`、内置默认值。不会隐式读取工作目录中的配置；开发时可显式使用 `--config ./config.toml`。首次 `start` 未找到默认配置时，会创建仅含注释的配置文件并采用默认值，不覆盖已有文件。

`start` 解析原生 `codex-auth.exe` 的真实位置，并以绝对路径传给后台进程，支持官方 npm 安装的嵌套或扁平依赖布局。也可在配置中直接指定：

```toml
[collector]
executable = 'C:\Tools\codex-auth.exe'
```

同一配置先前已成功解析的命令路径会保存在 `state/launch.json`，后续终端 PATH 缩短时仍可复用；切换命令或配置文件时会重新检查。后台运行不使用 SYSTEM 账户，只执行 `list --api --json`，不切换账户或消耗重置卡。

`service.log` 每个文件最多 1 MiB，保留 3 个备份。日志和状态不保存认证令牌、原始账户 JSON、邮箱或账户名称。状态只保存实例标识、进程号、健康心跳、最近成功采集时间和最近观察到的 USB 连接状态；进程号仅供诊断，不用于终止进程。

`status` 默认显示易读状态；`status --json` 输出 JSON，分别报告 `registered`、`enabled`、`process_running`、`usb_connected` 和 `last_success_at`。存活判断依赖跨进程命名互斥锁，不根据 PID 文件判断。健康记录超过 10 秒或进程未运行时，USB 状态为 `null`，表示未知；`true/false` 是最近一次传输观察结果，不代表持续进行硬件探测。

## 停止与恢复

`stop` 先禁用任务，阻止登录启动及崩溃重试，然后发送当前用户专属停止 Event。主循环停止请求采集，取消正在执行的采集子进程树，等待显示线程清屏、将亮度归零并释放资源后退出。Ctrl+C 和卸载任务使用相同的退出清理；重启时恢复配置亮度。没有连接设备时不重新连接来熄屏，没有运行实例时可安全重复执行。

正常退出等待上限为 30 秒；超时后只允许 Task Scheduler 终止这个受管理的任务，再等待 5 秒确认退出。命令会明确报告强制停止，并写入 `state/last-stop.json`。熄屏失败不阻止设备释放和进程退出；强制终止、崩溃或 USB 断连不能保证熄屏。停止结果的 `screen_off` 区分 `succeeded`（清屏和零亮度命令成功返回）、`failed`、`not_attempted`、`unknown`，与 `forced`、`cleanup_complete` 分开记录。实际背光熄灭仍需实机确认，不能据进程退出推断。不会根据任意 PID 终止 Python 或 Codex 进程；没有对应计划任务的挂起前台实例无法通过此回退强杀。

任务禁止并行实例和默认长期运行时限，允许电池供电，空闲状态结束不终止应用，并启用可用时补启动。进程异常退出时每隔 1 分钟重试，最多 3 次，避免快速无限崩溃循环。USB 拔出和 API 超时由既有重连与历史快照逻辑处理，不依赖重启进程。休眠恢复、实际任务重启行为仍需系统级验收。

## 前台调试与卸载

```powershell
auxdisp-codex-quota run
auxdisp-codex-quota run --config C:\Users\Me\auxdisp-config.toml
auxdisp-codex-quota preview
```

无子命令仅显示帮助。Windows 前台与后台共享同一用户互斥锁，防止争用设备；前台运行前应先停止后台。`preview` 不启动显示实例，其输出路径与行为见[PNG 预览](usage.md#png-预览)。各子命令的参数使用 `<子命令> --help` 查看。

卸载 Python 包前执行：

```powershell
auxdisp-codex-quota stop
auxdisp-codex-quota uninstall-service
pip uninstall auxdisp-codex-quota
```

`uninstall-service` 先停止实例再删除本用户的计划任务，保留配置、日志和诊断状态。安装升级本身不修改任务；升级后执行 `start` 或 `restart` 使任务与当前安装环境一致。
