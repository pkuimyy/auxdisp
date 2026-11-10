# auxdisp-driver

[中文版](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/README.md)

A standalone Python library for auxiliary displays: send Pillow images over USB / serial, control brightness and orientation, and retain upstream device-specific methods. Use it to build your own information-screen application.

## Features

Includes eight implementations: Rev A/B/C/D, Turing USB, WeAct A/B, and a local simulator. Supports image drawing, device-supported brightness/orientation controls, discovery, and public `LcdComm*` APIs. Capabilities vary by device.

## Installation

Requires Python 3.9+. Version 0.1.0 is published on [PyPI](https://pypi.org/project/auxdisp-driver/):

```powershell
pip install auxdisp-driver
```

Pillow, NumPy, PySerial, PyUSB, PyCryptodome, and `libusb-package` are installed as dependencies. End users do not need a source checkout or uv.

## Supported devices and protocol selection

| Family | `open_display()` identifier | Connection |
|---|---|---|
| Rev A / B / C / D | `rev_a` / `rev_b` / `rev_c` / `rev_d` | Serial |
| Turing USB | `turing_usb` | USB |
| WeAct A / B | `weact_a` / `weact_b` | Serial |
| Simulator | `simulated` | Local HTTP preview |

Select by actual device model, not only serial adapter IDs. A Turing USB 5.2-inch clear-screen fix is documented, but a complete Windows hardware matrix has not been accepted; preserving other drivers does not establish hardware compatibility. [Full device table and verification scope](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/supported-devices.md).

## Quick example

Requires an accessible Turing USB device. Image dimensions follow its current orientation. The context manager closes the device on exit; place an update loop inside the `with` block for continuous output.

```python
from PIL import Image, ImageDraw
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(30)
    image = Image.new("RGB", (display.width, display.height), "navy")
    ImageDraw.Draw(image).text((24, 24), "Hello AuxDisp", fill="white")
    display.show(image)
```

Select serial ports explicitly, for example `open_display("rev_a", com_port="COM5")`; use the corresponding device path on Linux/macOS. Without hardware, use `open_display("simulated", width=1280, height=720)` and keep the context open to view `http://localhost:5678`. The simulator also writes `screencap.png` in the working directory.

## Device discovery

```python
from auxdisp_driver import discover_devices

for candidate in discover_devices():
    print(candidate)
```

Discovery is passive by default: it does not open serial ports or wake devices. Candidates do not guarantee access; shared adapter IDs may yield several protocol candidates. `discover_devices(wake_devices=True)` explicitly enables Rev C wake-up; opening Rev C with `AUTO` also retains that sequence.

## Device-specific APIs

`Display` forwards device-specific methods, and the `LcdComm*` classes remain public. For example, a Rev B backplate LED:

```python
from auxdisp_driver import LcdCommRevB

lcd = LcdCommRevB(com_port="COM5")
try:
    lcd.InitializeComm()
    lcd.SetBackplateLedColor((32, 180, 255))
finally:
    lcd.closeSerial()
```

Turing USB retains H.264 streaming, file upload/playback, storage, and settings helpers. Capabilities and return conventions vary; consult the [API guide](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/architecture.md) and source before use.

## Platform requirements

| Platform | Requirements and limits |
|---|---|
| Windows | USB devices need a compatible interface driver; this package does not install or replace system device drivers. Serial devices need an accessible COM port. |
| Linux | USB / serial access permissions are required; device-specific rules may need administrator setup. |
| macOS | A working USB backend or serial path is required; verify model compatibility separately. |

`libusb-package` supplies a user-space library; it cannot replace Windows interface drivers or Linux permission setup. A system libusb may be used when needed. Installability does not establish hardware acceptance on each platform.

## Troubleshooting

If discovery finds nothing, check protocol/model, data cable, interface driver/permissions, and serial path. Candidates alone do not prove a connection. Catch `DisplayError` for connection or Turing USB transfer failures, release resources, then retry. For a blank screen, check brightness, orientation, and image size. [Detailed guide](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/usage.md).

## Documentation

- [Installation, examples, and discovery](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/usage.md)
- [Architecture and API](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/architecture.md)
- [Development and building](https://github.com/pkuimyy/auxdisp/blob/main/docs/en/development.md)
- [Issues](https://github.com/pkuimyy/auxdisp/issues) · [Releases](https://github.com/pkuimyy/auxdisp/releases)

## Credits and license

Primarily derived from [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) by Matthieu Houdebine and contributors. Licensed under [GPL-3.0-or-later](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/LICENSE); attribution and modifications are documented in [NOTICE](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md).
