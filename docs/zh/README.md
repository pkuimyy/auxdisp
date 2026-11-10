# AuxDisp

[English version](../en/README.md)

AuxDisp 为小型辅助显示屏提供 Python 驱动，支持通过 USB 或串口发送图像、设置亮度与显示方向。

- **显示驱动库**：包含 Rev A/B/C/D、Turing USB、WeAct A/B 和本地模拟器，保留设备专用 API。
- **[Codex 用量应用](../../apps/auxdisp-codex-quota/README.md)**：首版已实现，支持多账户轮播、额度展示与 USB 重连，正在实机验收。

驱动库 0.1.0 已发布到 PyPI，仍处于早期阶段。驱动代码的覆盖范围与实机兼容性请参阅[支持设备](../../packages/auxdisp-driver/docs/zh/supported-devices.md)。

### 文档

- [驱动库与使用示例](../../packages/auxdisp-driver/README.md)
- [项目架构](architecture.md)
- [本地开发与环境问题排查](development.md)
