# AuxDisp

[English version](../en/README.md)


AuxDisp 是一个 Git 单体仓库，用于维护彼此独立的 Python 发行包：用于驱动小型辅助屏的设备驱动库，以及未来的 Codex 用量显示应用。

| 项目 | 路径 | 发行包 | 状态 |
|---|---|---|---|
| 驱动库 | [`packages/auxdisp-driver`](../../packages/auxdisp-driver/README.md) | `auxdisp-driver` | 已完成提取；尚未发布到 PyPI |
| Codex 用量应用 | [`apps/auxdisp-codex-quota`](../../apps/auxdisp-codex-quota/README.md) | `auxdisp-codex-quota` | 工程占位项目，尚无用量业务代码 |

每个项目都是独立的 uv 项目，各自拥有 `pyproject.toml`、`uv.lock` 和 `.venv`。仓库刻意不使用 uv Workspace。Git 仓库只负责协作，不会在发行包之间建立源码依赖。

### 项目文档

- [架构](architecture.md)
- [驱动支持的设备](../../packages/auxdisp-driver/docs/zh/supported-devices.md)

参考仓库位于本 Git 历史之外，仅供只读分析。上游监控应用及有意未纳入的 `res/` 目录不属于 AuxDisp。
