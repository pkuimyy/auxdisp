# 更新日志

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/CHANGELOG.md)


### 0.1.0

- 将上游八类驱动提取为可安装的 Python 包。
- 保留串口、USB、图像转换、模拟器和设备专用命令。
- 移除对原应用日志配置和字体资源的运行时依赖。
- 所有平台均通过 `libusb-package` 提供 libusb 运行时。
- 增加轻量的设备发现、打开/关闭 API 和使用示例。
- 串口连接失败和 USB 传输失败通过 `DisplayError` 报告。
- 默认设备发现不唤醒 Rev C；可显式启用主动唤醒。
- 补全发行元数据并使用适合 PyPI 的绝对文档链接。
- 按 Turing USB 设备原生尺寸清屏，并重置本地图像状态，避免白条与局部刷新恢复旧画面。
