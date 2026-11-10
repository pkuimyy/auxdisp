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

### 用量应用的生命周期

应用目录目前只是元数据、文档和锁文件占位项目。驱动尚未发布，因此应用暂不启用对 `auxdisp-driver` 的运行时依赖。驱动通过设备验收并发布到 PyPI 后，应用可以声明有界的包索引版本要求，更新自己的 `uv.lock`，并运行 `uv lock --no-sources` 和 `uv sync --locked --no-sources`。

### CI 与发布

驱动 CI 独立测试并构建驱动。应用占位项目的 CI 只检查应用骨架，不会在驱动尚未发布时伪造 PyPI 集成测试。驱动的发布工作流仅由显式推送 `auxdisp-driver-v<版本>` tag 触发，上传 PyPI 后将同一份制品发布到 GitHub Release。配置与操作见[驱动发布](releases.md)。应用发布流程仍待其达到发布阶段后配置。
