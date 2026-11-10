"""Non-destructive visual/timing check for a Turing USB 5.2-inch display."""

import argparse
import time

from PIL import Image, ImageDraw

from auxdisp_driver import LcdCommTuringUSB, Orientation


def test_pattern(width: int, height: int, frame: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline="white", width=4)
    draw.rectangle((8, 8, width // 2, height - 9), fill="#ef4444")
    draw.rectangle((width // 2 + 1, 8, width - 9, height - 9), fill="#22c55e")
    draw.line((width // 2, 8, width // 2, height - 8), fill="white", width=3)
    draw.rectangle((16, 16, 72, 72), fill="#2563eb")
    draw.rectangle((width - 72, height - 72, width - 16, height - 16), fill="#facc15")
    draw.text((24, height // 2), f"Turing USB 5.2 | frame {frame}", fill="white")
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brightness", type=int, default=50, help="brightness percent (0-100)")
    parser.add_argument("--frames", type=int, default=3, help="number of complete frames to send")
    args = parser.parse_args()
    if not 0 <= args.brightness <= 100:
        parser.error("--brightness must be between 0 and 100")
    if args.frames < 1:
        parser.error("--frames must be at least 1")

    lcd = LcdCommTuringUSB()
    try:
        if lcd.dev_pid != 0x0050:
            raise RuntimeError(f"Expected Turing 5.2-inch PID 0x0050, found 0x{lcd.dev_pid:04x}")
        started = time.perf_counter()
        lcd.InitializeComm()
        print(f"H01/H02 identify + initialize: {time.perf_counter() - started:.3f}s")

        lcd.SetOrientation(Orientation.LANDSCAPE)
        if (lcd.get_width(), lcd.get_height()) != (1280, 720):
            raise RuntimeError(f"Expected landscape 1280x720, got {lcd.get_width()}x{lcd.get_height()}")
        lcd.SetBrightness(args.brightness)

        durations = []
        for frame in range(1, args.frames + 1):
            image = test_pattern(lcd.get_width(), lcd.get_height(), frame)
            start = time.perf_counter()
            lcd.DisplayPILImage(image)
            elapsed = time.perf_counter() - start
            durations.append(elapsed)
            print(f"Frame {frame}/{args.frames}: {elapsed:.3f}s")
        print(f"First frame: {durations[0]:.3f}s; mean full-frame send: {sum(durations) / len(durations):.3f}s")
        print("Inspect H03-H06 on screen: orientation, colors, borders, and corner markers.")
        print("H08 brightness was set to", args.brightness, "percent.")
    finally:
        lcd.close()
        print("USB resources released.")


if __name__ == "__main__":
    main()
