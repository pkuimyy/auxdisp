"""Installed application paths; never depend on the launcher's working directory."""

from dataclasses import dataclass
import os
from pathlib import Path


APP_ID = "auxdisp-codex-quota"


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @classmethod
    def current(cls):
        if os.name == "nt":
            location = os.environ.get("LOCALAPPDATA")
            if not location:
                raise OSError("LOCALAPPDATA is unavailable")
            root = Path(location) / APP_ID
        else:
            root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_ID
        return cls(root.resolve())

    @property
    def config(self):
        return self.root / "config.toml"

    @property
    def state(self):
        return self.root / "state/service.json"

    @property
    def log(self):
        return self.root / "logs/service.log"


def select_config(explicit=None, paths=None):
    if explicit is not None:
        return Path(explicit).resolve()
    default = (paths or AppPaths.current()).config
    return default if default.is_file() else None
