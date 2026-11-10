# auxdisp-driver

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/README.md)

独立的 Python 辅助显示屏驱动库：把 Pillow 图像发送到 USB / 串口屏幕，控制亮度与方向，并保留上游设备专用方法。适合开发自己的信息屏应用。

## 功能

包含 Rev A/B/C/D、Turing USB、WeAct A/B 和本地模拟器八类实现；支持图像绘制、设备支持的亮度/方向控制、设备发现，以及公开的 `LcdComm*` API。具体能力因设备而异。

## 安装

要求 Python 3.9+。0.1.0 已发布到 [PyPI](https://pypi.org/project/auxdisp-driver/):

```powershell
pip install auxdisp-driver
```

Pillow、NumPy、PySerial、PyUSB、PyCryptodome 与 `libusb-package` 会作为依赖安装。普通用户无需源码或 uv。

## 支持设备与选择协议

| 设备系列 | `open_display()` 标识符 | 连接 |
|---|---|---|
| Rev A / B / C / D | `rev_a` / `rev_b` / `rev_c` / `rev_d` | Serial |
| Turing USB | `turing_usb` | USB |
| WeAct A / B | `weact_a` / `weact_b` | Serial |
| 模拟器 | `simulated` | 本地 HTTP 预览 |

按实际型号选择协议，不要只根据串口适配器 ID 判断。已有 Turing USB 5.2 英寸清屏修复记录，但没有完整 Windows 硬件矩阵通过的结论；其他驱动的代码保留也不等于实机可用。 [完整设备表与验收范围](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md).

## 快速示例

以下示例需要可访问的 Turing USB 设备，图像尺寸取自当前方向。`with` 会在退出时关闭设备；若要持续显示和更新，可把循环放在 `with` 块内。

```python
from PIL import Image, ImageDraw
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(30)
    image = Image.new("RGB", (display.width, display.height), "navy")
    ImageDraw.Draw(image).text((24, 24), "Hello AuxDisp", fill="white")
    display.show(image)
```

串口设备可显式指定端口，例如 `open_display("rev_a", com_port="COM5")`；Linux/macOS 使用对应设备路径。没有硬件可用 `open_display("simulated", width=1280, height=720)`，在 `with` 内等待时可访问 `http://localhost:5678`；模拟器也会在工作目录写入 `screencap.png`。

## 设备发现

```python
from auxdisp_driver import discover_devices

for candidate in discover_devices():
    print(candidate)
```

默认被动枚举，不打开串口、不唤醒设备；结果是候选项，不保证可访问。共享适配器 ID 可能产生多个协议候选。`discover_devices(wake_devices=True)` 显式启用 Rev C 唤醒；以 `AUTO` 打开 Rev C 也保留唤醒流程。

## 设备专用 API

`Display` 转发专用方法，也可直接使用 `LcdComm*` 类。例如 Rev B 背板灯：

```python
from auxdisp_driver import LcdCommRevB

lcd = LcdCommRevB(com_port="COM5")
try:
    lcd.InitializeComm()
    lcd.SetBackplateLedColor((32, 180, 255))
finally:
    lcd.closeSerial()
```

Turing USB 的 H.264 流、文件上传/播放、存储及设置方法仍保留；各设备能力与返回约定不同，使用前阅读 [API 说明](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/architecture.md) 及源码。

## 平台要求

| 系统 | 要求与限制 |
|---|---|
| Windows | USB 设备需兼容的接口驱动；Python 包不会安装或替换系统设备驱动。串口需可访问的 COM 端口。 |
| Linux | 需 USB / 串口访问权限；必要时由管理员按设备设置规则。 |
| macOS | 需可用的 USB 后端或串口路径，设备兼容性单独验证。 |

`libusb-package` 提供用户态 libusb 库，不能替代 Windows USB 接口驱动或 Linux 权限设置。必要时可使用系统 libusb。可安装到某系统并不表示所有设备已通过该系统验收。

## 故障排查

发现不到设备时，检查协议型号、USB 数据线、接口驱动/权限及串口路径；不要仅凭候选列表认定连接成功。连接或 Turing USB 传输失败可捕获 `DisplayError`，释放后重试。画面为空时检查亮度、方向和图像尺寸。 [详细指南](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/usage.md).

## 更多文档

- [安装、示例与设备发现](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/usage.md)
- [架构与 API](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/architecture.md)
- [开发与构建](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)
- [Issues](https://github.com/pkuimyy/auxdisp/issues) · [Releases](https://github.com/pkuimyy/auxdisp/releases)

## 来源与许可证

主要源自 Matthieu Houdebine 及贡献者的 [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)。 许可证为 [GPL-3.0-or-later](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/LICENSE)，来源和修改记录见 [NOTICE](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md).
