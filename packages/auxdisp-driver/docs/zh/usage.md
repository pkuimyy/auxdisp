# auxdisp-driver — 驱动使用指南

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/usage.md)


这是从 [`turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python) 提取的独立 Python 显示驱动包。它保留上游 `LcdComm*` API 和设备专用方法，移除了系统监控器、主题、配置界面及应用资源。许可证为 GPL-3.0-or-later，详见 [NOTICE.md](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md)。

### 安装

要求 Python 3.9+，普通用户可直接从 PyPI 安装 0.1.0：

```powershell
pip install auxdisp-driver
```

依赖 Pillow、NumPy、PySerial、PyUSB、PyCryptodome 和 `libusb-package` 会自动安装。后者提供用户态 libusb 库，不替代 Windows 设备接口驱动或 Linux 设备权限；必要时可使用系统 libusb。平台与硬件验收范围见[支持设备](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md)。

源码开发另见[本地开发](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)，在 `packages/auxdisp-driver` 同步独立环境。

### 驱动显示屏

根据设备型号选择协议。部分旧款串口设备共用 USB 转串口 ID，因此自动发现可能返回多个候选项；遇到这种情况时，请明确选择正确驱动。

```python
from PIL import Image
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(50)
    display.show(Image.new("RGB", (display.width, display.height), "navy"))
```

底层类仍公开供设备专用操作使用：

```python
from auxdisp_driver import LcdCommRevB

lcd = LcdCommRevB(com_port="COM5")
try:
    lcd.InitializeComm()
    lcd.SetBackplateLedColor((32, 180, 255))
finally:
    lcd.closeSerial()
```

对于 Turing USB 设备，`LcdCommTuringUSB` 还保留上游的视频流、文件上传与播放、存储操作和厂商命令辅助方法。这些操作因设备而异，使用前请查看对应文档字符串和源码。

### 示例

在此源码目录完成 `uv sync --locked` 后运行：

```powershell
uv run python examples\simulated_display.py
uv run python examples\turing_usb_52.py --brightness 50 --frames 3
```

模拟器会在当前工作目录写入 `screencap.png`，并通过 `http://localhost:5678` 提供预览。5.2 英寸示例检查 VID `0x1CBE`、PID `0x0050`，设置横屏，显示颜色和边界图案，重复发送全屏画面并计时，退出时释放 PyUSB 资源。它不会重置固件或修改设备存储。

### 设备发现

```python
from auxdisp_driver import discover_devices

for candidate in discover_devices():
    print(candidate)
```

设备发现只是探测，不保证设备一定可访问，也不代表每个型号都已完成实机测试。协议覆盖范围和实机验证状态见[支持的设备](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md)。

默认发现不打开串口或唤醒设备。需要主动唤醒 Rev C 时，显式调用 `discover_devices(wake_devices=True)`；此操作可能等待设备重新枚举。打开 Rev C 的 `AUTO` 端口时也会执行原有唤醒流程。

连接和 Turing USB 传输失败可通过 `DisplayError` 捕获；调用方可在处理错误后释放设备或重新连接：

```python
from auxdisp_driver import DisplayError, open_display

try:
    with open_display("turing_usb") as display:
        display.set_brightness(50)
except DisplayError as exc:
    print(f"Display unavailable: {exc}")
```

### 构建

```powershell
uv build --no-sources
```

wheel 包含驱动源码和许可证，不会在运行时依赖任何参考仓库。0.1.0 已发布到 PyPI。
