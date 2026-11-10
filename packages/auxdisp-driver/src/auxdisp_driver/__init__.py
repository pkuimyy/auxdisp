"""Standalone drivers for small smart displays.

The low-level ``LcdComm*`` classes intentionally retain the upstream method
names and device-specific methods.  ``open_display`` is a small convenience
factory; callers can also instantiate the driver classes directly.
"""

from auxdisp_driver.display import Display, DisplayInfo, discover_devices, open_display
from auxdisp_driver.exceptions import DisplayError
from auxdisp_driver.lcd.lcd_comm import Orientation
from auxdisp_driver.lcd.lcd_comm_rev_a import LcdCommRevA
from auxdisp_driver.lcd.lcd_comm_rev_b import LcdCommRevB
from auxdisp_driver.lcd.lcd_comm_rev_c import LcdCommRevC
from auxdisp_driver.lcd.lcd_comm_rev_d import LcdCommRevD
from auxdisp_driver.lcd.lcd_comm_turing_usb import LcdCommTuringUSB
from auxdisp_driver.lcd.lcd_comm_weact_a import LcdCommWeActA
from auxdisp_driver.lcd.lcd_comm_weact_b import LcdCommWeActB
from auxdisp_driver.lcd.lcd_simulated import LcdSimulated

__all__ = [
    "Display", "DisplayError", "DisplayInfo", "Orientation", "discover_devices", "open_display",
    "LcdCommRevA", "LcdCommRevB", "LcdCommRevC", "LcdCommRevD", "LcdCommTuringUSB",
    "LcdCommWeActA", "LcdCommWeActB", "LcdSimulated",
]
