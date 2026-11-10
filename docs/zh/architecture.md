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

### 驱动

`packages/auxdisp-driver/src/auxdisp_driver/` 包含提取后的 `LcdComm*` 协议类，以及轻量的设备发现和打开封装。协议代码尽量保持上游实现。驱动包不包含 Codex 或系统监控业务逻辑。所有平台都通过 `libusb-package` 提供 libusb 运行时；Windows USB 设备仍需绑定兼容的 USB 接口驱动，Linux 用户仍需有设备访问权限。

### 用量应用

驱动 0.1.0 已完成基础实机验证并发布到 PyPI。用量应用以 `auxdisp-driver>=0.1.0,<0.2.0` 声明普通包索引依赖，独立维护锁文件，不导入驱动源码目录。应用已实现只读采集、不可变历史快照、账户轮播、Pillow 渲染和独立 USB 重连线程，详见[应用使用与架构](../../apps/auxdisp-codex-quota/docs/zh/usage.md)。

### CI 与发布

驱动 CI 独立测试并构建驱动。应用 CI 从 PyPI 安装驱动，独立测试、构建，并验证应用 wheel 安装与离线预览。驱动的发布工作流仅由显式推送 `auxdisp-driver-v<版本>` tag 触发，上传 PyPI 后将同一份制品发布到 GitHub Release。配置与操作见[驱动发布](releases.md)。应用发布流程仍待其达到发布阶段后配置。
