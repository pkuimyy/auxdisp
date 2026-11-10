# auxdisp-codex-quota

[English version](../en/README.md)

在 Turing USB 5.2 英寸屏幕上轮播多个 Codex 账户的剩余额度：1280×720 横屏、固定日期时钟、10 格进度条和异常状态。

要求 Python 3.11+、已安装并配置账户的 `codex-auth`，以及可访问的 USB 设备。驱动依赖从 PyPI 安装，当前应用为首次验收版本。

### 安装与运行

发行包安装后，可使用当前用户的 Windows 计划任务常驻运行：

```powershell
auxdisp-codex-quota start
auxdisp-codex-quota status
auxdisp-codex-quota stop
auxdisp-codex-quota restart
```

安装包本身不会创建任务。首次 `start` 才注册任务；配置默认读取 `%LOCALAPPDATA%\auxdisp-codex-quota\config.toml`。详见 [Windows 后台运行与卸载](background.md)。本次实现不代表已发布新的 PyPI 版本。

源码开发在 `apps/auxdisp-codex-quota` 目录执行：

```powershell
uv sync --locked --no-sources
uv run --locked --no-sources auxdisp-codex-quota run --config config.example.toml
```

默认每 60 秒采集、每 15 秒切换账户，屏幕亮度为 30%。退出使用 Ctrl+C。应用只调用 `codex-auth list --api --json`，不会切换账户或使用重置额度。

`config.toml` 保存刷新周期、亮度和按稳定账户 ID 设置的特殊额度策略，不保存认证令牌。缺失的额度默认显示 `UNAVAILABLE`；只有明确配置的窗口才显示 `NOT LIMITED`。

### 离线预览

```powershell
uv run --locked --no-sources auxdisp-codex-quota --preview preview.png
```

预览默认使用合成账户，不访问账户或 USB。更多配置、预览场景和测试说明见[使用指南](usage.md)。
