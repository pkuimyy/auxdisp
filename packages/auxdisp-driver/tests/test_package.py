import importlib
import unittest
from pathlib import Path

from PIL import Image

import auxdisp_driver as package
from auxdisp_driver.display import DRIVERS, Display
from auxdisp_driver.lcd import lcd_comm_turing_usb, lcd_simulated
from auxdisp_driver.lcd.lcd_comm import LcdComm
from auxdisp_driver.lcd.serialize import image_to_RGB565


class PackageTests(unittest.TestCase):
    def test_every_driver_imports(self):
        expected = {"rev_a", "rev_b", "rev_c", "rev_d", "turing_usb", "weact_a", "weact_b", "simulated"}
        self.assertEqual(set(DRIVERS), expected)
        for module in (
            "lcd_comm_rev_a", "lcd_comm_rev_b", "lcd_comm_rev_c", "lcd_comm_rev_d",
            "lcd_comm_turing_usb", "lcd_comm_weact_a", "lcd_comm_weact_b", "lcd_simulated",
        ):
            importlib.import_module(f"auxdisp_driver.lcd.{module}")
        self.assertTrue(package.open_display)

    def test_driver_source_has_no_original_application_imports(self):
        source_root = Path(__file__).parents[1] / "src" / "auxdisp_driver"
        for file in source_root.rglob("*.py"):
            self.assertNotIn("from library.", file.read_text(encoding="utf-8"), str(file))
            self.assertNotIn("import library.", file.read_text(encoding="utf-8"), str(file))

    def test_rgb565_known_pixel_and_endianness(self):
        image = Image.new("RGB", (1, 1), (255, 0, 0))
        self.assertEqual(image_to_RGB565(image, "big"), b"\xf8\x00")
        self.assertEqual(image_to_RGB565(image, "little"), b"\x00\xf8")

    def test_default_upstream_font_falls_back_without_res(self):
        class FontLcd(LcdComm):
            def InitializeComm(self): pass
            def Reset(self): pass
            def Clear(self): pass
            def ScreenOff(self): pass
            def ScreenOn(self): pass
            def SetBrightness(self, level): pass
            def SetOrientation(self, orientation): pass
            def DisplayPILImage(self, image, x=0, y=0, image_width=0, image_height=0): pass

        lcd = FontLcd.__new__(FontLcd)
        lcd.font_cache = {}
        font = lcd.open_font("./res/fonts/roboto/Roboto-Black.ttf", 14)
        self.assertIsNotNone(font)
        self.assertEqual(len(lcd.font_cache), 1)

    def test_usb_packet_shape_and_resource_release(self):
        packet = lcd_comm_turing_usb.encrypt_command_packet(bytearray(500))
        self.assertEqual(len(packet), 512)
        self.assertEqual(packet[-2:], b"\xa1\x1a")

        released = []
        device = object()
        lcd = lcd_comm_turing_usb.LcdCommTuringUSB.__new__(lcd_comm_turing_usb.LcdCommTuringUSB)
        lcd.dev = device
        original = lcd_comm_turing_usb.usb.util.dispose_resources
        try:
            lcd_comm_turing_usb.usb.util.dispose_resources = released.append
            lcd.close()
        finally:
            lcd_comm_turing_usb.usb.util.dispose_resources = original
        self.assertEqual(released, [device])
        self.assertIsNone(lcd.dev)

    def test_display_wrapper_forwards_calls_and_closes(self):
        class FakeDevice:
            def get_width(self):
                return 10

            def get_height(self):
                return 20

            def DisplayPILImage(self, image, x=0, y=0):
                self.last = (image, x, y)

            def closeSerial(self):
                self.closed = True

        device = FakeDevice()
        image = Image.new("RGB", (1, 1))
        with Display(device) as display:
            self.assertEqual((display.width, display.height), (10, 20))
            display.show(image, 2, 3)
        self.assertEqual(device.last, (image, 2, 3))
        self.assertTrue(device.closed)

    def test_simulated_display_writes_image_and_closes(self):
        path = Path(__file__).parent / "screencap-test.png"
        original_file = lcd_simulated.SCREENSHOT_FILE
        original_port = lcd_simulated.WEBSERVER_PORT
        lcd_simulated.SCREENSHOT_FILE = str(path)
        lcd_simulated.WEBSERVER_PORT = 0
        lcd = None
        server = None
        thread = None
        try:
            lcd = lcd_simulated.LcdSimulated(display_width=16, display_height=12)
            lcd.DisplayPILImage(Image.new("RGB", (16, 12), "red"))
            self.assertTrue(path.exists())
            server = lcd.webServer
            thread = lcd.webServerThread
            with Image.open(path) as screenshot:
                self.assertEqual(screenshot.getpixel((0, 0)), (255, 0, 0))
        finally:
            if lcd is not None:
                lcd.closeSerial()
                self.assertIsNone(lcd.webServer)
                self.assertIsNone(lcd.webServerThread)
                self.assertFalse(thread.is_alive())
                self.assertEqual(server.fileno(), -1)
            lcd_simulated.SCREENSHOT_FILE = original_file
            lcd_simulated.WEBSERVER_PORT = original_port


if __name__ == "__main__":
    unittest.main()
