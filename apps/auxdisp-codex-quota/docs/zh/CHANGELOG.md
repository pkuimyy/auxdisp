# auxdisp-codex-quota — 更新日志

[English version](../en/CHANGELOG.md)

### 未发布

- 增加当前用户 Windows 计划任务与 start/stop/status/restart/run/uninstall-service 命令。
- 增加命名互斥锁、正常停止信号、采集取消、有限崩溃重试和用户目录轮转日志。
- 配置默认切换为当前用户数据目录；开发目录配置需显式 `--config`。
- 按 TUI v3 调整为紧凑单行 Header、分列细进度条与固定 Footer。
- 账户名称与百分比使用 44px，其余文字统一为 24px；采用等宽字体和中文名称回退，长文本省略。
- Footer 保留轮播索引、READ ONLY、API 状态和 LAST OK，移除采集及轮播周期提示。
- 增加横排资源栏，未接入的数据明确显示 `N/A`；保留现有采集、轮播与 USB 行为。

### 0.1.0

- 从 PyPI 依赖已发布的 auxdisp-driver。
- 实现只读采集、窗口解析、历史快照与多账户轮播。
- 增加固定时钟、10 格额度条、离线预览与 USB 自动重连。
- 增加合成数据、异常恢复和安装验证测试。
