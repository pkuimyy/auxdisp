# auxdisp-driver

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/README.md)

独立的 Python 辅助显示屏驱动库，支持 Rev A/B/C/D、Turing USB、WeAct A/B 和本地模拟器，保留上游 `LcdComm*` API 与设备专用方法。

要求 Python 3.9 或更新版本。0.1.0 已发布到 PyPI，可使用 `pip install auxdisp-driver` 安装；项目仍处于早期阶段。Windows USB 设备需要兼容的接口驱动，Linux 用户需要相应的设备访问权限。

### 使用示例

安装后，选择与设备匹配的协议即可发送 Pillow 图像。以下示例适用于 Turing USB 设备：

```python
from PIL import Image
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(50)
    display.show(Image.new("RGB", (display.width, display.height), "navy"))
```

### 文档

- [支持设备](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md)
- [安装、设备发现与更多示例](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/usage.md)
- [架构与 API](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/architecture.md)
- [本地开发与构建](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)

源自 [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)，许可证为 GPL-3.0-or-later。详见 [NOTICE.md](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md) 和 [LICENSE](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/LICENSE)。
