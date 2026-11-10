# auxdisp-codex-quota — 配置与开发说明

[English version](../en/usage.md) | [返回介绍](README.md)

## 数据来源

应用按 [codex-auth JSON API schema 1](https://github.com/Loongphy/codex-auth/blob/main/docs/json-api.md) 执行 `codex-auth list --api --json`，不会使用 `--active` 或任何切换、重置、删除账户的命令。额外 JSON 字段被忽略，未知协议版本会显示错误并保留历史数据。应用不读取或保存认证令牌。

先独立安装并配置 `codex-auth`。Windows npm 安装会自动定位官方包内的原生 `codex-auth.exe`（兼容嵌套与扁平依赖布局），以便超时或退出时终止其进程树。其他安装方式可在配置中填写原生可执行文件的完整路径。命令未安装、JSON 无效、超时或退出异常时，显示安全错误代码，不回显原始 stdout/stderr。

## 本地配置

配置依次选择显式 `--config <路径>`、`%LOCALAPPDATA%\auxdisp-codex-quota\config.toml` 和内置默认值，不再自动读取当前工作目录。开发时可用 `--config config.example.toml`，或先复制示例后显式指定本地配置文件；已有配置无需覆盖。文件只包含显示设置及稳定账户 ID，不含令牌。常驻命令、日志和卸载步骤见 [Windows 后台运行](background.md)。

| 配置 | 默认值 |
|---|---|
| `collector.executable` | `codex-auth` |
| `collector.refresh_seconds` | 60 秒 |
| `collector.timeout_seconds` | 20 秒 |
| `rotation.seconds` | 15 秒 |
| `display.orientation` | `landscape`（固定 1280×720） |
| `display.brightness` | 30% |
| `display.reconnect_seconds` | 5 秒 |
| `render.thresholds` | `[75, 50, 25]` |
| `render.font` | 空字符串，使用系统字体 |
| `logging.level` | `INFO` |

百分比显示最多两位小数。格数按实际剩余百分比向上取整，每 10% 一格；未知数据与 0% 分开显示。只按 `window_minutes=300/10080` 识别 5 小时和 7 天窗口，其他窗口保留在模型中，不误映射。

界面采用固定 1280×720 的紧凑 TUI 排版：账户名称、套餐、ACTIVE/INACTIVE、STALE 与日期时间位于同一行；额度区按窗口、10 格细条、百分比和重置时间分列。进度条固定高 21px，Footer 固定展示轮播索引、READ ONLY、API 状态和 LAST OK，保留资源栏下方的留白。

字号使用 44px（账户名称、百分比）和 24px（日期时间、资源数值、标签、状态及其他信息）。默认使用等宽字体，中文名称使用同字号系统字体回退；`render.font` 可指定字体文件。长名称和状态说明在预留区域内省略，不缩小字号。CREDITS、RESET CARDS、NEXT EXPIRY 资源栏当前显示 `N/A`，尚未接入资源字段，不能据此判断余额或卡片数量。

用以下只读命令查看规范化数据和稳定 `account_key`，该输出包含账户身份信息，请勿公开：

```powershell
uv run --locked --no-sources auxdisp-codex-quota --inspect
```

明确知道某个账户不限制 5 小时额度时，在本地配置添加：

```toml
[accounts."这里填写完整 account_key"]
unlimited_windows = [300]
```

该策略仅按稳定 ID 生效，不从邮箱后缀、缺失的窗口或 `secondary=null` 推断。缺失窗口默认 `UNAVAILABLE`；明确配置才显示 `NOT LIMITED`。

## 离线与无硬件运行

```powershell
# 三张合成数据预览；不读取真实账户、不使用 USB
uv run --locked --no-sources auxdisp-codex-quota --preview previews/dual.png
uv run --locked --no-sources auxdisp-codex-quota --preview previews/single.png --account-index 1
uv run --locked --no-sources auxdisp-codex-quota --preview previews/error.png --simulate-error

# 演示轮播，60 秒后退出；只写最新 PNG
uv run --locked --no-sources auxdisp-codex-quota --demo --headless previews/latest.png --duration 60
```

`--fixture <JSON路径>` 可替换内置合成数据。`--headless <PNG路径>` 单独使用时仍采集真实账户，仅替换 USB 输出；配合 `--demo` 才完全离线。`--duration` 用于有界集成测试；省略时持续运行，Ctrl+C 退出并释放资源。

## 实现结构

| 模块 | 职责 |
|---|---|
| `collector.py` | 唯一只读命令、超时/进程树取消、单采集线程和单结果槽 |
| `model.py` | 协议解析、不可变账户快照、失败合并、稳定 ID 轮播 |
| `config.py` | TOML 设置和显式账户策略 |
| `render.py` | 独立页面模型、固定时钟位置、文字裁切和 10 格额度条 |
| `display.py` | 独立 USB 线程、只保留最新帧、断线重试与同帧去重 |
| `runtime.py` | 60 秒采集、15 秒轮播、分钟时钟及可见内容去重 |
| `cli.py` | 正常启动、预览、只读检查和有界测试 |
| `paths.py` | 全局安装后的用户配置、日志与状态目录 |
| `service.py` / `scheduler.py` | 幂等 CLI 生命周期和当前用户计划任务 |
| `win32.py` / `host.py` | 单实例互斥锁、停止 Event、健康心跳和轮转日志 |
| `_background.py` | 计划任务专用的安装包内部运行入口 |

采集、页面调度和 USB 传输互不阻塞。无账户也显示时钟；整体请求失败保留全部历史数据，单账户失败仅保留该账户历史并标记 `STALE`。最近请求成功时间与 `usage.updated_at` 分开保存。账户顺序变化保留当前稳定 ID；移除当前账户时优先选择旧顺序中的下一个存活账户。

## 测试与限制

在本项目目录执行：

```powershell
uv sync --locked --all-groups --no-sources
uv run --locked --no-sources ruff check src tests
uv run --locked --no-sources pytest
uv build --no-sources
```

`auxdisp-codex-quota` CI 独立构建，始终从 PyPI 安装 `auxdisp-driver`，不使用 monorepo 路径依赖；测试和预览只用合成账户与伪设备。虚拟环境与共享缓存约定见[本地开发](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)。

当前只支持一块 Turing USB 5.2 英寸设备与 Landscape 布局。USB 重连依靠最近一帧重试；操作系统 USB 调用本身可能短暂阻塞显示线程。75 秒集成运行不能代替长时间稳定性验证。首次人工验收前不扩展 GUI、账户管理、动画或其他屏幕型号。
