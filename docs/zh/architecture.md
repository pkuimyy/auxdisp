# 架构

[English version](../en/architecture.md)


```text
Git 仓库：auxdisp
├── packages/auxdisp-driver     独立的 PyPI 驱动发行包
│       └── USB / 串口显示协议
└── apps/auxdisp-codex-quota    未来的独立 PyPI 应用
        └── 依赖已发布的 auxdisp-driver
```

两个目录共享 Git 历史，但各自管理 Python 依赖解析、锁文件、虚拟环境和发布周期。仓库不配置 uv Workspace。驱动通过验收并发布后，应用必须使用驱动稳定的公开 API 和普通 PEP 508 版本范围；不得直接导入驱动的 `src/` 目录。

### auxdisp-driver

`packages/auxdisp-driver/src/auxdisp_driver/` 包含提取后的 `LcdComm*` 协议类，以及轻量的设备发现和打开封装。协议代码尽量保持上游实现。驱动包不包含 Codex 或系统监控业务逻辑。所有平台都通过 `libusb-package` 提供 libusb 运行时；Windows USB 设备仍需绑定兼容的 USB 接口驱动，Linux 用户仍需有设备访问权限。

### auxdisp-codex-quota

`auxdisp-driver` 0.1.0 已完成基础实机验证并发布到 PyPI。`auxdisp-codex-quota` 以 `auxdisp-driver>=0.1.0,<0.2.0` 声明普通包索引依赖，独立维护锁文件，不导入驱动源码目录。应用已实现只读采集、不可变历史快照、账户轮播、Pillow 渲染和独立 USB 重连线程，详见[auxdisp-codex-quota 使用与架构](../../apps/auxdisp-codex-quota/docs/zh/usage.md)。

`auxdisp-codex-quota` 支持当前用户 Windows 计划任务和 CLI 生命周期管理，使用安装环境的 `pythonw.exe`、单实例互斥锁和正常停止 Event。配置与轮转日志放在用户数据目录；详见 [Windows 后台运行](../../apps/auxdisp-codex-quota/docs/zh/background.md)。真实任务注册、登录恢复与 USB 插拔仍需系统/实机验收。

### CI 与发布

`auxdisp-driver` CI 独立测试并构建 `auxdisp-driver`。`auxdisp-codex-quota` CI 从 PyPI 安装 `auxdisp-driver`，独立测试、构建，并验证 `auxdisp-codex-quota` wheel 安装与离线预览。`auxdisp-driver` 的发布工作流仅由显式推送 `auxdisp-driver-v<版本>` tag 触发，上传 PyPI 后将同一份制品发布到 GitHub Release。配置与操作见[auxdisp-driver 发布](releases.md)。`auxdisp-codex-quota` 通过独立的 `auxdisp-codex-quota-release.yml` 发布，由 `auxdisp-codex-quota-v<版本>` tag 触发；详见[应用发布说明](../../apps/auxdisp-codex-quota/docs/zh/releases.md)。
