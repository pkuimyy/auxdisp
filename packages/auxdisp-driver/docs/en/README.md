# AuxDisp Driver

[中文版](../zh/README.md)

An independent Python package containing the display drivers extracted from [`turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python). It retains the upstream `LcdComm*` APIs and device-specific methods while omitting the system monitor, themes, configuration UI, and bundled application resources. The package is GPL-3.0-or-later; see [NOTICE.md](../../NOTICE.md).

### Install

For development in this monorepo:

```powershell
uv sync --locked
```

The first PyPI release has not happened yet. After release, consumer applications can install `auxdisp-driver` from PyPI with their normal package installer.

The package requires Python 3.9 or newer, Pillow, NumPy, PySerial, PyUSB, and PyCryptodome. Dependencies are declared for the full driver set, including serial, USB, image conversion, and encrypted Turing USB protocols.

This package installs `libusb-package` on all platforms as the libusb runtime and uses it to discover USB devices. Windows devices still need a compatible USB interface driver; the wheel does not install or replace that system driver. Linux users must still have permission to access USB devices; if the bundled backend does not fit the system environment, a system libusb installation can be used. macOS users may also use a system libusb installation.

### Use a display

Choose the protocol for the model you own. Some legacy serial devices share USB-to-serial IDs, so automatic discovery can return more than one candidate; select the correct driver explicitly when that applies.

```python
from PIL import Image
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(50)
    display.show(Image.new("RGB", (display.width, display.height), "navy"))
```

The low-level classes remain public for device-specific operations:

```python
from auxdisp_driver import LcdCommRevB

lcd = LcdCommRevB(com_port="COM5")
try:
    lcd.InitializeComm()
    lcd.SetBackplateLedColor((32, 180, 255))
finally:
    lcd.closeSerial()
```

For Turing USB devices, the `LcdCommTuringUSB` class also retains upstream video streaming, file upload/playback, storage, and vendor command helpers. These operations are device-specific; read their docstrings/source before use.

### Examples

From this source checkout after `uv sync --locked`:

```powershell
uv run python examples\simulated_display.py
uv run python examples\turing_usb_52.py --brightness 50 --frames 3
```

The simulator writes `screencap.png` in its current working directory and serves it at `http://localhost:5678`. The 5.2-inch example checks VID `0x1CBE`, PID `0x0050`, sets landscape orientation, displays a color/boundary chart, repeats full-frame sends, times them, and releases PyUSB resources when it exits. It does not reset firmware or modify device storage.

### Device discovery

```python
from auxdisp_driver import discover_devices

for candidate in discover_devices():
    print(candidate)
```

Discovery is a probe, not a guarantee that a device is accessible. It does not claim that every model has been tested on physical hardware. See [`supported-devices.md`](supported-devices.md) for protocol coverage and the current hardware verification boundary.

### Build

```powershell
uv build --no-sources
```

The wheel contains the package source and license and has no runtime path dependency on either reference checkout. This project has not been uploaded to PyPI.
