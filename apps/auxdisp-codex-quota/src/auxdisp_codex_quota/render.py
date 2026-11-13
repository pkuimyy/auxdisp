"""Deterministic 1280x720 pages with fixed clock and ten-segment quota bars."""

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from unicodedata import east_asian_width

from PIL import Image, ImageDraw, ImageFont

from .config import Settings
from .model import Snapshot


FONT_LARGE = 44
FONT_MEDIUM = 24
FONT_SMALL = FONT_MEDIUM

BG = "#10151e"
FG = "#e9edf4"
MUTED = "#9aa9bd"
DIM = "#67778d"
RULE = "#344257"
TRACK = "#2a3443"
COLORS = ("#40db86", "#ffd018", "#ff9845", "#ff6672")

CANVAS = (1280, 720)
LEFT, RIGHT = 48, 1232
HEADER_Y, HEADER_RULE_Y = 74, 122
TITLE_WIDTH, PLAN_WIDTH, HEADER_GAP = 530, 96, 16
DATE_RIGHT, TIME_RIGHT = 1133, RIGHT
COLUMNS_Y = 178
ROW_CENTERS = (244, 332)
ROW_RULE_Y = 290
BAR_X, BAR_WIDTH, BAR_HEIGHT, BAR_GAP = 222, 380, 21, 9
PERCENT_RIGHT = 760
RESET_RIGHT = 1048
RESOURCES_RULE_Y, RESOURCES_Y = 392, 436
FOOTER_RULE_Y, FOOTER_Y = 648, 675
COUNTER_WIDTH, META_X = 196, 276
HEALTH_X, HEALTH_TEXT_X, REASON_X, HEALTH_RIGHT = 560, 576, 730, 856


def timestamp(value, now=None):
    if value is None:
        return "--"
    try:
        return datetime.fromtimestamp(value, tz=now.tzinfo if now else None).astimezone(
            now.tzinfo if now else None).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "--"


def time_left(value, now, elapsed="EXPIRED"):
    if value is None:
        return "--"
    seconds = value - now.timestamp()
    if seconds <= 0:
        return elapsed
    minutes = math.ceil(seconds / 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    return f"{days}d {hours}h" if days else (f"{hours}h {minutes}m" if hours else f"{minutes}m")


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
    countdown: str = "--"


@dataclass(frozen=True)
class CardRow:
    title: str
    expiry: str
    countdown: str


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
    reset_cards: str = "N/A"
    cards: tuple[CardRow, ...] = ()
    card_page: str = ""


def make_page(snapshot: Snapshot, current: str | None, now: datetime, settings: Settings,
              *, card_page_index: int | None = None) -> Page:
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
                rows.append(Row(label, "known", value + "%", filled, color, "Reset " + timestamp(window.resets_at, now),
                                time_left(window.resets_at, now, "DUE")))
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
    cards = sorted(account.reset_cards, key=lambda c: (c.expires_at is None, c.expires_at or 0)) if account else []
    card_pages = max(1, math.ceil(len(cards) / 3))
    # Complete one card cycle within an account rotation, avoiding skipped pages
    # when account count and card-page count share a common factor.
    card_index = int((now.timestamp() % settings.rotation_seconds) * card_pages / settings.rotation_seconds)
    if card_page_index is not None:
        card_index = max(0, min(card_page_index, card_pages - 1))
    card_rows = tuple(CardRow(f"{c.title} [{c.status}]", timestamp(c.expires_at, now),
                             time_left(c.expires_at, now)) for c in cards[card_index * 3:card_index * 3 + 3])
    return Page(
        now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
        next((i + 1 for i, a in enumerate(snapshot.accounts) if a.key == current), 0), len(snapshot.accounts),
        account.key if account else "", account.alias or account.email or account.key if account else "",
        account.plan.upper() if account else "", bool(account and account.active), stale, tuple(rows),
        "API ERROR" if failed else ("API OK" if snapshot.last_success_at else "API WAIT"), detail,
        snapshot.last_success_at.astimezone().strftime("%Y-%m-%d %H:%M") if snapshot.last_success_at else "--",
        empty,
        str(account.reset_credits) if account and account.reset_credits is not None else "N/A",
        card_rows, f"{card_index + 1}/{card_pages}" if cards else "",
    )


class Renderer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fonts = {}

    def font(self, size, bold=False, cjk=False):
        key = (size, bold, cjk)
        if key not in self.fonts:
            candidates = [self.settings.font] if self.settings.font else []
            if cjk:
                # Keep CJK account names readable at the same configured size.
                candidates += [
                    "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                ]
            candidates += [
                "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
                "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf",
            ]
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
        image = Image.new("RGB", CANVAS, BG)
        draw = ImageDraw.Draw(image)

        def text(x, y, value, size=FONT_SMALL, color=FG, width=None, bold=False, anchor="lm"):
            value = " ".join(value.split())
            font = self.font(size, bold, cjk=any(east_asian_width(char) in "WF" for char in value))
            if width is not None and draw.textlength(value, font=font) > width:
                ellipsis = "…"
                if draw.textlength(ellipsis, font=font) > width:
                    return 0
                while value and draw.textlength(value + ellipsis, font=font) > width:
                    value = value[:-1]
                value += ellipsis
            draw.text((x, y), value, font=font, fill=color, anchor=anchor)
            return draw.textlength(value, font=font)

        title_width = text(LEFT, HEADER_Y, page.title or "CODEX QUOTA", FONT_LARGE,
                           width=TITLE_WIDTH, bold=True)
        if not page.empty:
            plan_x = LEFT + title_width + HEADER_GAP
            plan_width = text(plan_x, HEADER_Y, page.plan, color=MUTED, width=PLAN_WIDTH)
            state_x = plan_x + plan_width + HEADER_GAP
            text(state_x, HEADER_Y, "ACTIVE" if page.active else "INACTIVE",
                 color=COLORS[0] if page.active else MUTED)
            # Reserve the longer INACTIVE label even on active/error pages.
            stale_x = state_x + draw.textlength("INACTIVE", font=self.font(FONT_SMALL)) + HEADER_GAP
            if page.stale:
                text(stale_x, HEADER_Y, "STALE", color=COLORS[1])
        text(DATE_RIGHT, HEADER_Y, page.date, FONT_MEDIUM, MUTED, anchor="rm")
        text(TIME_RIGHT, HEADER_Y, page.clock, FONT_MEDIUM, anchor="rm")
        draw.line((LEFT, HEADER_RULE_Y, RIGHT, HEADER_RULE_Y), fill=RULE)

        text(LEFT, COLUMNS_Y, "WINDOW", color=DIM)
        text(BAR_X, COLUMNS_Y, "REMAINING", color=DIM)
        text(PERCENT_RIGHT, COLUMNS_Y, "LEFT", color=DIM, anchor="rm")
        text(RESET_RIGHT, COLUMNS_Y, "RESET AT", color=DIM, anchor="rm")
        text(RIGHT, COLUMNS_Y, "RESET IN", color=DIM, anchor="rm")
        if page.empty:
            text(LEFT, ROW_CENTERS[0], page.empty, FONT_LARGE, MUTED, width=RIGHT - LEFT)
        else:
            draw.line((LEFT, ROW_RULE_Y, RIGHT, ROW_RULE_Y), fill=TRACK)
            for row, y in zip(page.rows, ROW_CENTERS):
                text(LEFT, y, row.label)
                reset = row.reset.removeprefix("Reset ") if row.state == "known" else "—"
                text(RESET_RIGHT, y, reset, color=MUTED, anchor="rm")
                text(RIGHT, y, row.countdown, color=MUTED, anchor="rm")
                if row.state == "known":
                    for i in range(10):
                        x = BAR_X + round(i * (BAR_WIDTH + BAR_GAP) / 10)
                        end = BAR_X + round((i + 1) * (BAR_WIDTH + BAR_GAP) / 10) - BAR_GAP - 1
                        top = y - BAR_HEIGHT // 2
                        draw.rectangle((x, top, end, top + BAR_HEIGHT - 1),
                                       fill=row.color if i < row.filled else TRACK)
                    text(PERCENT_RIGHT, y, row.percent, FONT_LARGE, row.color, bold=True, anchor="rm")
                else:
                    label = "DATA UNAVAILABLE" if row.state == "UNAVAILABLE" else row.state
                    text(BAR_X, y, label, color=COLORS[0] if row.state == "NOT LIMITED" else MUTED,
                         width=PERCENT_RIGHT - BAR_X)

        draw.line((LEFT, RESOURCES_RULE_Y, RIGHT, RESOURCES_RULE_Y), fill=RULE)
        text(LEFT, RESOURCES_Y, "RESET CARDS", color=MUTED)
        text(238, RESOURCES_Y, page.reset_cards, width=160)
        text(RIGHT, RESOURCES_Y, "RESET CARDS PAGES " + (page.card_page or "--"),
             color=MUTED, anchor="rm")
        text(LEFT, 478, "CARD / STATUS", color=DIM)
        text(RESET_RIGHT, 478, "EXPIRES AT", color=DIM, anchor="rm")
        text(RIGHT, 478, "EXPIRES IN", color=DIM, anchor="rm")
        for card, y in zip(page.cards, (518, 562, 606)):
            text(LEFT, y, card.title, width=700)
            text(RESET_RIGHT, y, card.expiry, color=MUTED, anchor="rm")
            text(RIGHT, y, card.countdown, color=MUTED, anchor="rm")
        if not page.cards:
            text(LEFT, 518, "NO CARD DETAILS" if page.reset_cards != "N/A" else "N/A", color=MUTED)

        draw.line((LEFT, FOOTER_RULE_Y, RIGHT, FOOTER_RULE_Y), fill=RULE)
        text(LEFT, FOOTER_Y, f"ACCOUNT {page.index}/{page.total}", width=COUNTER_WIDTH)
        text(META_X, FOOTER_Y, "READ ONLY", color=DIM, width=HEALTH_X - META_X - HEADER_GAP)
        health_color = COLORS[3] if page.status == "API ERROR" else (COLORS[0] if page.status == "API OK" else MUTED)
        draw.ellipse((HEALTH_X, FOOTER_Y - 4, HEALTH_X + 8, FOOTER_Y + 4), fill=health_color)
        text(HEALTH_TEXT_X, FOOTER_Y, page.status, color=health_color)
        reason = page.detail.removeprefix("STALE / ")
        if reason == "STALE":
            reason = ""
        reason = reason.replace("ACCOUNT REFRESH FAILED / ", "").replace("ACCOUNT REFRESH FAILED", "REFRESH")
        text(REASON_X, FOOTER_Y, reason, color=COLORS[1], width=HEALTH_RIGHT - REASON_X)
        text(RIGHT, FOOTER_Y, "LAST OK " + page.last_ok, color=MUTED, anchor="rm")
        return image


def save_preview(image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same-directory replacement preserves the old file if encoding fails.
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".auxdisp-codex-quota-", suffix=".png", delete=False) as file:
            temporary = Path(file.name)
            image.save(file, format="PNG")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
