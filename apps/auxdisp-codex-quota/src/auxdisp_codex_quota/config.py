"""Validated, token-free TOML application settings."""

from dataclasses import dataclass, field
from pathlib import Path
import logging
import math
import tomllib


@dataclass(frozen=True)
class Settings:
    executable: str = "codex-auth"
    refresh_seconds: float = 60
    timeout_seconds: float = 20
    rotation_seconds: float = 15
    brightness: int = 30
    reconnect_seconds: float = 5
    thresholds: tuple[float, float, float] = (75, 50, 25)
    font: str = ""
    log_level: str = "INFO"
    unlimited: dict[str, frozenset[int]] = field(default_factory=dict)


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        return Settings()
    with path.open("rb") as file:
        data = tomllib.load(file)
    for key in data:
        if key not in {"collector", "rotation", "display", "render", "logging", "accounts"}:
            raise ValueError(f"Unknown configuration section: {key}")
        if not isinstance(data[key], dict):
            raise ValueError(f"{key} must be a table")
    collector, rotation, display, render, logs = (data.get(key, {}) for key in (
        "collector", "rotation", "display", "render", "logging",
    ))
    executable = collector.get("executable", "codex-auth")
    font = render.get("font", "")
    if not isinstance(executable, str) or not executable.strip() or not isinstance(font, str):
        raise ValueError("Executable and font must be strings; executable must not be empty")
    if display.get("orientation", "landscape") != "landscape":
        raise ValueError("Only landscape 1280x720 is supported")
    brightness = display.get("brightness", 30)
    if type(brightness) is not int or not 0 <= brightness <= 100:
        raise ValueError("brightness must be an integer between 0 and 100")
    thresholds = render.get("thresholds", [75, 50, 25])
    if (not isinstance(thresholds, list) or len(thresholds) != 3
            or any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in thresholds)
            or not 100 >= thresholds[0] > thresholds[1] > thresholds[2] >= 0):
        raise ValueError("thresholds must contain three descending numbers between 0 and 100")
    level = logs.get("level", "INFO")
    if not isinstance(level, str) or level.upper() not in logging.getLevelNamesMapping():
        raise ValueError("Invalid logging level")
    unlimited = {}
    for key, policy in data.get("accounts", {}).items():
        if not key or not isinstance(policy, dict):
            raise ValueError("Account policy must be a table keyed by account_key")
        windows = policy.get("unlimited_windows", [])
        if not isinstance(windows, list) or any(type(x) is not int or x not in (300, 10080) for x in windows):
            raise ValueError("unlimited_windows may contain 300 and 10080 only")
        unlimited[key] = frozenset(windows)
    return Settings(
        executable=executable,
        refresh_seconds=positive(collector.get("refresh_seconds", 60), "refresh_seconds"),
        timeout_seconds=positive(collector.get("timeout_seconds", 20), "timeout_seconds"),
        rotation_seconds=positive(rotation.get("seconds", 15), "rotation.seconds"),
        brightness=brightness, reconnect_seconds=positive(display.get("reconnect_seconds", 5), "reconnect_seconds"),
        thresholds=tuple(thresholds), font=font, log_level=level.upper(), unlimited=unlimited,
    )
