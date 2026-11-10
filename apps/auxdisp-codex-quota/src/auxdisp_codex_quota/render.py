"""Deterministic 1280x720 pages with fixed clock and ten-segment quota bars."""

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import Settings
from .model import Snapshot


BG = "#10151f"
FG = "#eef2f7"
MUTED = "#94a3b8"
COLORS = ("#4ade80", "#facc15", "#fb923c", "#f87171")


def timestamp(value):
    if value is None:
        return "--"
    try:
        return datetime.fromtimestamp(value).astimezone().strftime("%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "--"


def quota_style(remaining, thresholds=(75, 50, 25)):
    if remaining is None:
        return 0, MUTED
    count = math.ceil(remaining / 10)
    index = next((i for i, threshold in enumerate(thresholds) if remaining >= threshold), 3)
    return count, COLORS[index]


@dataclass(frozen=True)
class Row:
    label: str
    state: str
    percent: str
    filled: int
    color: str
    reset: str


@dataclass(frozen=True)
class Page:
    date: str
    clock: str
    index: int
    total: int
    key: str
    title: str
    plan: str
    active: bool
    stale: bool
    rows: tuple[Row, ...]
    status: str
    detail: str
    last_ok: str
    empty: str = ""


def make_page(snapshot: Snapshot, current: str | None, now: datetime, settings: Settings) -> Page:
    account = next((a for a in snapshot.accounts if a.key == current), None)
    rows = []
    if account:
        for minutes, label in ((300, "5 HOUR"), (10080, "7 DAYS")):
            window = next((w for w in account.windows if w.minutes == minutes), None)
            if minutes in settings.unlimited.get(account.key, ()):
                rows.append(Row(label, "NOT LIMITED", "", 0, MUTED, "Account policy"))
            elif window is None or window.remaining is None:
                rows.append(Row(label, "UNAVAILABLE", "", 0, MUTED, "Reset --"))
            else:
                filled, color = quota_style(window.remaining, settings.thresholds)
                value = f"{window.remaining:.2f}".rstrip("0").rstrip(".")
                rows.append(Row(label, "known", value + "%", filled, color, "Reset " + timestamp(window.resets_at)))
    account_error = account is not None and account.refresh_status != "ok"
    failed = snapshot.error is not None or account_error
    detail = snapshot.error or ("ACCOUNT REFRESH FAILED" if account_error else "")
    if account_error and account.refresh_http_status is not None and not snapshot.error:
        detail += f" / HTTP {account.refresh_http_status}"
    stale = bool(account and (account.stale or snapshot.error))
    if stale:
        detail = "STALE" + (" / " + detail if detail else "")
    empty = ""
    if account is None:
        empty = "DATA UNAVAILABLE" if snapshot.error else (
            "NO ACCOUNTS" if snapshot.last_success_at is not None else "WAITING FOR DATA"
        )
    return Page(
        now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
        next((i + 1 for i, a in enumerate(snapshot.accounts) if a.key == current), 0), len(snapshot.accounts),
        account.key if account else "", account.alias or account.email or account.key if account else "",
        account.plan.upper() if account else "", bool(account and account.active), stale, tuple(rows),
        "API ERROR" if failed else ("API OK" if snapshot.last_success_at else "API WAIT"), detail,
        snapshot.last_success_at.astimezone().strftime("%Y-%m-%d %H:%M") if snapshot.last_success_at else "--",
        empty,
    )


class Renderer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fonts = {}

    def font(self, size, mono=False):
        key = (size, mono)
        if key not in self.fonts:
            candidates = ([self.settings.font] if self.settings.font else []) + (
                ["C:/Windows/Fonts/consola.ttf", "DejaVuSansMono.ttf"] if mono else
                ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"]
            )
            for candidate in candidates:
                try:
                    self.fonts[key] = ImageFont.truetype(candidate, size)
                    break
                except OSError:
                    continue
            else:
                self.fonts[key] = ImageFont.load_default(size=size)
        return self.fonts[key]

    def render(self, page: Page) -> Image.Image:
        image = Image.new("RGB", (1280, 720), BG)
        draw = ImageDraw.Draw(image)

        def text(x, y, value, size, color=FG, width=None, mono=False, anchor="la"):
            value = " ".join(value.split())
            font = self.font(size, mono)
            if width is not None and draw.textlength(value, font=font) > width:
                while value and draw.textlength(value + "…", font=font) > width:
                    value = value[:-1]
                value += "…"
            draw.text((x, y), value, font=font, fill=color, anchor=anchor)

        text(48, 36, "CODEX QUOTA", 28)
        text(600, 47, f"{page.index} / {page.total}", 24, MUTED, mono=True, anchor="ma")
        text(1232, 25, page.date, 24, MUTED, mono=True, anchor="ra")
        text(1232, 56, page.clock, 64, mono=True, anchor="ra")
        draw.line((48, 145, 1232, 145), fill="#334155", width=2)
        if page.empty:
            text(48, 295, page.empty, 48, MUTED)
        else:
            text(48, 177, page.title, 48, width=1010)
            text(48, 245, page.plan, 24, MUTED, width=700)
            if page.active:
                text(1232, 190, "ACTIVE", 22, COLORS[0], anchor="ra")
            if page.stale:
                text(1232, 245, "STALE", 22, COLORS[1], anchor="ra")
            for row, y in zip(page.rows, (306, 468)):
                text(48, y, row.label, 26, MUTED, mono=True)
                text(1232, y, row.reset, 22, MUTED, anchor="ra")
                if row.state == "known":
                    for i in range(10):
                        x = 48 + i * 90
                        draw.rectangle((x, y + 49, x + 77, y + 107), fill=row.color if i < row.filled else "#283241")
                    text(1232, y + 43, row.percent, 56, row.color, mono=True, anchor="ra")
                else:
                    text(48, y + 47, row.state, 40, MUTED)
        draw.line((48, 635, 1232, 635), fill="#334155", width=2)
        text(48, 651, page.status, 24, COLORS[3] if page.status == "API ERROR" else COLORS[0])
        text(1232, 655, "LAST OK " + page.last_ok, 20, MUTED, anchor="ra")
        text(48, 687, page.detail, 18, COLORS[1], width=1184)
        return image


def save_preview(image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
