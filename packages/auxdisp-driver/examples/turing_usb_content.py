"""Display text, drawing primitives, and gradients on a Turing USB screen."""

import argparse
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from auxdisp_driver import Orientation, open_display


def font(size: int):
    for name in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"):
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def render(scene: str, width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "#101827")
    draw = ImageDraw.Draw(image)
    sx, sy = width / 1280, height / 720

    def box(bounds, **kwargs):
        x0, y0, x1, y1 = bounds
        draw.rectangle((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)), **kwargs)

    def text(x, y, value, size=32, fill="white"):
        draw.text((int(x * sx), int(y * sy)), value, font=font(max(1, int(size * sy))), fill=fill)

    if scene == "text":
        text(48, 32, "AuxDisp / Text rendering", 48)
        text(48, 140, "Hello, Turing USB!", 64, "#38bdf8")
        text(48, 252, "辅助显示屏：中英文文字测试", 48)
        text(48, 358, "0123456789   ABCDEFG   abcdefg", 38)
        text(48, 450, "Small text / 小字号", 22, "#cbd5e1")
        text(48, 534, f"Landscape: {width} x {height}", 34, "#4ade80")
        text(48, 620, "Pillow bitmap -> auxdisp-driver -> USB", 24, "#94a3b8")
    elif scene == "graphics":
        text(48, 32, "AuxDisp / Shapes and progress bars", 44)
        for index, (value, color) in enumerate(((25, "#38bdf8"), (50, "#4ade80"), (85, "#fbbf24"))):
            y = 150 + index * 125
            text(48, y, f"{value}%", 36)
            box((190, y, 1180, y + 64), fill="#263449")
            box((190, y, 190 + 990 * value / 100, y + 64), fill=color)
        for index, color in enumerate(("#ef4444", "#22c55e", "#3b82f6", "#facc15")):
            x = 220 + index * 240
            draw.ellipse((int(x * sx), int(555 * sy), int((x + 100) * sx), int(655 * sy)), fill=color)
        text(48, 660, "Synthetic drawing test / 合成图形测试", 22, "#cbd5e1")
    else:
        text(48, 32, "AuxDisp / RGB gradients and grid", 44)
        for x in range(width):
            level = round(x * 255 / max(1, width - 1))
            for index, color in enumerate(((level, 0, 0), (0, level, 0), (0, 0, level), (level, level, level))):
                y = int((140 + index * 110) * sy)
                draw.line((x, y, x, y + int(85 * sy)), fill=color)
        for x in range(0, width, max(1, width // 16)):
            draw.line((x, int(600 * sy), x, height - 1), fill="#94a3b8")
        for y in range(int(600 * sy), height, max(1, int(24 * sy))):
            draw.line((0, y, width - 1, y), fill="#94a3b8")
    draw.rectangle((0, 0, width - 1, height - 1), outline="white", width=2)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=("all", "text", "graphics", "gradient"), default="all")
    parser.add_argument("--hold", type=float, default=5, help="seconds to keep each scene visible")
    parser.add_argument("--output-dir", type=Path, help="optional directory for reference PNG files")
    args = parser.parse_args()
    if args.hold < 0:
        parser.error("--hold must be non-negative")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    scenes = ("text", "graphics", "gradient") if args.scene == "all" else (args.scene,)
    with open_display("turing_usb", orientation=Orientation.LANDSCAPE) as display:
        display.set_brightness(50)
        for scene in scenes:
            image = render(scene, display.width, display.height)
            if args.output_dir:
                image.save(args.output_dir / f"{scene}.png")
            start = time.perf_counter()
            display.show(image)
            print(f"{scene}: {display.width}x{display.height}, {time.perf_counter() - start:.3f}s", flush=True)
            time.sleep(args.hold)
    print("USB resources released; the last scene remains on screen.")


if __name__ == "__main__":
    main()
