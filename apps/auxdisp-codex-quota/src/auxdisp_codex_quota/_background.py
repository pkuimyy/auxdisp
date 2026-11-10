"""Private pythonw entry point for the current user's installed scheduled task."""

import argparse
from dataclasses import replace
import logging
from pathlib import Path

from .collector import CollectionWorker, Collector
from .config import load_settings
from .display import DisplayAdapter, DisplayWorker
from .host import file_logging, run_host
from .paths import AppPaths
from .render import Renderer
from .runtime import Runtime
from .win32 import InstanceBusy


def main(argv=None):
    parser = argparse.ArgumentParser(prog="auxdisp-codex-quota internal background host")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--executable", required=True, type=Path)
    args = parser.parse_args(argv)
    paths = AppPaths.current()
    try:
        if not args.config.is_absolute() or not args.executable.is_absolute():
            raise ValueError("Absolute paths required")
        settings = replace(load_settings(args.config), executable=str(args.executable))
        runtime = Runtime(settings, CollectionWorker(Collector(settings.executable, settings.timeout_seconds)),
                          Renderer(settings), DisplayWorker(DisplayAdapter(
                              settings.brightness, settings.reconnect_seconds,
                          )))
        run_host(runtime, paths=paths, background=True)
        return 0
    except InstanceBusy:
        return 0
    except Exception as exc:
        with file_logging(paths, "INFO"):
            # Neither raw subprocess output nor arbitrary exception messages enter logs.
            logging.error("Background host failed (%s); Task Scheduler may retry", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
