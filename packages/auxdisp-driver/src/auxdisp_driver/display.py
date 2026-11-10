"""Convenience discovery and lifecycle helpers around the upstream drivers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from auxdisp_driver.exceptions import DisplayError
from auxdisp_driver.lcd.lcd_comm import LcdComm, Orientation
from auxdisp_driver.lcd.lcd_comm_rev_a import LcdCommRevA
from auxdisp_driver.lcd.lcd_comm_rev_b import LcdCommRevB
from auxdisp_driver.lcd.lcd_comm_rev_c import LcdCommRevC
from auxdisp_driver.lcd.lcd_comm_rev_d import LcdCommRevD
from auxdisp_driver.lcd.lcd_comm_turing_usb import LcdCommTuringUSB, PRODUCT_ID, VENDOR_ID
from auxdisp_driver.lcd.lcd_comm_weact_a import LcdCommWeActA
from auxdisp_driver.lcd.lcd_comm_weact_b import LcdCommWeActB
from auxdisp_driver.lcd.lcd_simulated import LcdSimulated
from auxdisp_driver.usb_backend import find_usb_devices


DRIVERS: Dict[str, Type[LcdComm]] = {
    "rev_a": LcdCommRevA,
    "rev_b": LcdCommRevB,
    "rev_c": LcdCommRevC,
    "rev_d": LcdCommRevD,
    "turing_usb": LcdCommTuringUSB,
    "weact_a": LcdCommWeActA,
    "weact_b": LcdCommWeActB,
    "simulated": LcdSimulated,
}


@dataclass(frozen=True)
class DisplayInfo:
    """A detected display candidate; choose its driver explicitly to open it."""

    driver: str
    connection: str
    width: Optional[int] = None
    height: Optional[int] = None
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None


class Display:
    """Small context-manager wrapper that leaves the low-level driver intact."""

    def __init__(self, device: LcdComm):
        self.device = device

    @property
    def width(self) -> int:
        return self.device.get_width()

    @property
    def height(self) -> int:
        return self.device.get_height()

    def show(self, image: Any, x: int = 0, y: int = 0) -> None:
        self.device.DisplayPILImage(image, x=x, y=y)

    def set_orientation(self, orientation: Orientation) -> None:
        self.device.SetOrientation(orientation)

    def set_brightness(self, level: int) -> None:
        self.device.SetBrightness(level)

    def close(self) -> None:
        close = getattr(self.device, "close", None)
        if callable(close):
            close()
        else:
            self.device.closeSerial()

    def __enter__(self) -> "Display":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        # Keep all protocol-specific APIs available through the wrapper.
        return getattr(self.device, name)


def discover_devices(*, include_simulated: bool = False, wake_devices: bool = False) -> List[DisplayInfo]:
    """List candidates without opening ports or configuring USB by default.

    ``wake_devices=True`` opts into the upstream Rev C serial wake-up sequence.
    Opening a Rev C device with ``com_port="AUTO"`` also retains that sequence.
    """
    found: List[DisplayInfo] = []
    serial_drivers = ("rev_a", "rev_b", "rev_c", "rev_d", "weact_a", "weact_b")
    for key in serial_drivers:
        driver = DRIVERS[key]
        try:
            if key == "rev_c":
                port = driver.auto_detect_com_port(wake=wake_devices)
            else:
                port = driver.auto_detect_com_port()
        except Exception as exc:
            raise DisplayError(f"Could not probe serial ports for {key}: {exc}") from exc
        if port:
            found.append(DisplayInfo(driver=key, connection=str(port)))

    try:
        import usb.core
        for dev in find_usb_devices(find_all=True, idVendor=VENDOR_ID) or ():
            dimensions = PRODUCT_ID.get(int(dev.idProduct))
            if dimensions:
                width, height = dimensions
                found.append(DisplayInfo(
                    driver="turing_usb", connection="USB", width=width, height=height,
                    vendor_id=VENDOR_ID, product_id=int(dev.idProduct),
                ))
    except usb.core.NoBackendError as exc:
        raise DisplayError("USB discovery needs a working libusb backend") from exc

    if include_simulated:
        found.append(DisplayInfo(driver="simulated", connection="local"))
    return found


def open_display(
    driver: str,
    *,
    com_port: str = "AUTO",
    width: Optional[int] = None,
    height: Optional[int] = None,
    orientation: Optional[Orientation] = None,
    initialize: bool = True,
    **driver_options: Any,
) -> Display:
    """Construct the selected upstream driver and optionally initialize it."""
    try:
        driver_class = DRIVERS[driver.lower()]
    except (AttributeError, KeyError) as exc:
        raise DisplayError(f"Unknown driver {driver!r}; choose from {', '.join(DRIVERS)}") from exc

    options = dict(driver_options)
    options["com_port"] = com_port
    if width is not None:
        options["display_width"] = width
    if height is not None:
        options["display_height"] = height
    device: Optional[LcdComm] = None
    try:
        device = driver_class(**options)
        if initialize:
            device.InitializeComm()
        if orientation is not None:
            device.SetOrientation(orientation)
        return Display(device)
    except Exception as exc:
        if device is not None:
            close = getattr(device, "close", None)
            try:
                if callable(close):
                    close()
                elif hasattr(device, "closeSerial"):
                    device.closeSerial()
            except Exception:
                # Keep the initialization error as the exception reported to the caller.
                pass
        raise DisplayError(f"Failed to open {driver!r} display: {exc}") from exc
