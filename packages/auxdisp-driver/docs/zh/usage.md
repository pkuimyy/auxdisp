# auxdisp-driver — 驱动使用指南

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/usage.md)


这是从 [`turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python) 提取的独立 Python 显示驱动包。它保留上游 `LcdComm*` API 和设备专用方法，移除了系统监控器、主题、配置界面及应用资源。许可证为 GPL-3.0-or-later，详见 [NOTICE.md](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md)。

### 安装

从源码运行时，先进入 `packages/auxdisp-driver` 目录；开发环境配置见[本地开发文档](https://github.com/pkuimyy/auxdisp/blob/main/docs/zh/development.md)。同步依赖：

```powershell
uv sync --locked
```

0.1.0 已发布到 PyPI，可使用 `pip install auxdisp-driver` 安装。源码开发仍使用上述独立 uv 项目。

本包要求 Python 3.9 或更新版本，并依赖 Pillow、NumPy、PySerial、PyUSB 和 PyCryptodome。这些依赖覆盖完整驱动集所需的串口、USB、图像转换及 Turing USB 加密协议。

本包会在所有平台安装 `libusb-package` 作为 libusb 运行时，并通过它查找 USB 设备。Windows 设备仍需绑定兼容的 USB 接口驱动；wheel 不会安装或替换该系统驱动。Linux 用户仍需确保当前账户有 USB 设备访问权限；若打包的后端不适用于系统环境，可使用系统 libusb。macOS 用户也可使用系统安装的 libusb。

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
