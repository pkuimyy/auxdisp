# 更新日志

[English version](../en/CHANGELOG.md)


### 0.1.0

- 将上游八类驱动提取为可安装的 Python 包。
- 保留串口、USB、图像转换、模拟器和设备专用命令。
- 移除对原应用日志配置和字体资源的运行时依赖。
- 所有平台均通过 `libusb-package` 提供 libusb 运行时。
- 增加轻量的设备发现、打开/关闭 API 和使用示例。
