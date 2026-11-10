"""Render a small Pillow image through the local simulated LCD."""

from PIL import Image, ImageDraw

from auxdisp_driver import LcdSimulated, Orientation


def main() -> None:
    lcd = LcdSimulated(display_width=480, display_height=320)
    try:
        lcd.InitializeComm()
        lcd.SetOrientation(Orientation.LANDSCAPE)
        image = Image.new("RGB", (lcd.get_width(), lcd.get_height()), "#101827")
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, image.width - 9, image.height - 9), outline="white", width=3)
        draw.rectangle((12, 12, image.width // 2, image.height - 13), fill="#e33b45")
        draw.rectangle((image.width // 2, 12, image.width - 13, image.height - 13), fill="#28a878")
        draw.text((24, 24), "Turing display driver", fill="white")
        lcd.DisplayPILImage(image)
        print("Preview: http://localhost:5678 (screencap.png in the current directory)")
        input("Press Enter to stop the simulator... ")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
