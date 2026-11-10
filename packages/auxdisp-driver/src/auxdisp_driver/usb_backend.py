"""Use the packaged libusb runtime for PyUSB across supported platforms."""

from typing import Any

import libusb_package

def find_usb_devices(*args: Any, **kwargs: Any) -> Any:
    """Find USB devices using libusb-package's bundled or system backend."""
    return libusb_package.find(*args, **kwargs)
