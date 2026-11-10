# auxdisp-driver

[中文版](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/README.md)

An independent Python driver library for small auxiliary displays. Supports Rev A/B/C/D, Turing USB, WeAct A/B, and a local simulator, preserving upstream `LcdComm*` APIs and device-specific methods.

Requires Python 3.9 or newer. Version 0.1.0 is available on PyPI: install with `pip install auxdisp-driver`. The project remains at an early stage. Windows USB devices require a compatible interface driver; Linux users need device access permissions.

### Usage example

After installation, select the protocol matching your device and send a Pillow image. This example is for Turing USB devices:

```python
from PIL import Image
from auxdisp_driver import Orientation, open_display

with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
    display.set_brightness(50)
    display.show(Image.new("RGB", (display.width, display.height), "navy"))
```

### Documentation

- [Supported devices](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/supported-devices.md)
- [Installation, discovery, and more examples](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/usage.md)
- [Architecture and API](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/architecture.md)
- [Local development and building](https://github.com/pkuimyy/auxdisp/blob/main/docs/en/development.md)

Derived from [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python), licensed under GPL-3.0-or-later. See [NOTICE.md](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/NOTICE.md) and [LICENSE](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/LICENSE).
