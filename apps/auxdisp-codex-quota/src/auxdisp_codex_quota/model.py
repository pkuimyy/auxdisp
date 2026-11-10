"""Immutable snapshots shared by collection, scheduling, and rendering."""

from dataclasses import dataclass, replace
from datetime import datetime
import math
from typing import Any


class DataError(ValueError):
    """A safe error code, never a raw command response or credential."""


@dataclass(frozen=True)
class Window:
    minutes: int | None
    remaining: float | None
    resets_at: float | None


@dataclass(frozen=True)
class Account:
    key: str
    email: str = ""
    alias: str = ""
    plan: str = "UNKNOWN"
    active: bool = False
    windows: tuple[Window, ...] = ()
    source: str = "none"
    updated_at: float | None = None
    refresh_status: str = "unknown"
    refresh_http_status: int | None = None
    last_success_at: datetime | None = None

    @property
    def stale(self) -> bool:
        return bool(self.windows) and (self.refresh_status != "ok" or self.source == "cache")


@dataclass(frozen=True)
class Snapshot:
    accounts: tuple[Account, ...] = ()
    last_success_at: datetime | None = None
    error: str | None = None


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, OverflowError):
        return None


def text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def parse_accounts(document: Any) -> tuple[Account, ...]:
    if not isinstance(document, dict):
        raise DataError("INVALID_DOCUMENT")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise DataError("SCHEMA_UNSUPPORTED")
    if "error" in document:
        raise DataError("API_ERROR_DOCUMENT")
    if document.get("command") != "list" or not isinstance(document.get("accounts"), list):
        raise DataError("INVALID_LIST_DOCUMENT")
    accounts = []
    keys = set()
    for item in document["accounts"]:
        if not isinstance(item, dict) or not isinstance(item.get("account_key"), str) or not item["account_key"]:
            raise DataError("ACCOUNT_KEY_MISSING")
        key = item["account_key"]
        if key in keys:
            raise DataError("DUPLICATE_ACCOUNT_KEY")
        keys.add(key)
        usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
        refresh = usage.get("refresh") if isinstance(usage.get("refresh"), dict) else {}
        windows = []
        for field in ("primary", "secondary"):
            raw = usage.get(field)
            if not isinstance(raw, dict):
                continue
            minutes = number(raw.get("window_minutes"))
            minutes = int(minutes) if minutes is not None and minutes > 0 and minutes.is_integer() else None
            used = number(raw.get("used_percent"))
            windows.append(Window(minutes, None if used is None else min(100.0, max(0.0, 100 - used)),
                                  number(raw.get("resets_at"))))
        accounts.append(Account(
            key=key, email=text(item.get("email")), alias=text(item.get("alias")),
            plan=text(item.get("plan"), "UNKNOWN") or "UNKNOWN", active=item.get("active") is True,
            windows=tuple(windows), source=text(usage.get("source"), "none"),
            updated_at=number(usage.get("updated_at")), refresh_status=text(refresh.get("status"), "unknown"),
            refresh_http_status=refresh.get("http_status") if type(refresh.get("http_status")) is int else None,
        ))
    return tuple(accounts)


class AccountStore:
    """The scheduler alone commits complete, immutable collection results."""

    def __init__(self):
        self.snapshot = Snapshot()

    def success(self, accounts: tuple[Account, ...], now: datetime) -> None:
        previous = {account.key: account for account in self.snapshot.accounts}
        merged = []
        for account in accounts:
            old = previous.get(account.key)
            if account.refresh_status == "ok":
                account = replace(account, last_success_at=now)
            elif old:
                account = replace(
                    account, windows=old.windows or account.windows,
                    source="cache" if old.windows else account.source,
                    updated_at=old.updated_at if old.windows else account.updated_at,
                    last_success_at=old.last_success_at,
                )
            merged.append(account)
        self.snapshot = Snapshot(tuple(merged), now)

    def failure(self, error: str) -> None:
        self.snapshot = replace(self.snapshot, error=error)


class PageController:
    def __init__(self, interval: float):
        self.interval = interval
        self.keys: tuple[str, ...] = ()
        self.current: str | None = None
        self.deadline = 0.0

    def update(self, accounts: tuple[Account, ...], now: float) -> None:
        keys = tuple(account.key for account in accounts)
        old = self.keys
        if self.current not in keys:
            candidates = ()
            if self.current in old:
                index = old.index(self.current)
                candidates = old[index + 1:] + old[:index]
            self.current = next((key for key in candidates if key in keys), keys[0] if keys else None)
            self.deadline = now + self.interval
        elif len(old) < 2 <= len(keys):
            self.deadline = now + self.interval
        self.keys = keys

    def tick(self, now: float) -> None:
        if len(self.keys) > 1 and now >= self.deadline:
            count = int((now - self.deadline) // self.interval) + 1
            self.current = self.keys[(self.keys.index(self.current) + count) % len(self.keys)]
            self.deadline += count * self.interval
