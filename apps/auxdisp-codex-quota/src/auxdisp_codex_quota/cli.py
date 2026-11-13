"""User commands for lifecycle control, foreground display, and offline preview."""

import argparse
import json
import logging
from pathlib import Path

from .collector import CollectionWorker, Collector
from .config import load_settings
from .display import DisplayAdapter, DisplayWorker
from .host import run_host
from .model import DataError
from .paths import select_config
from .preview import write_preview
from .render import Renderer
from .runtime import Runtime
from .service import ServiceController
from .win32 import ServiceError


def build_parser():
    parser = argparse.ArgumentParser(
        prog="auxdisp-codex-quota", description="Codex account quotas on a Turing USB 5.2-inch display",
    )
    commands = parser.add_subparsers(dest="command", title="commands")
    descriptions = {
        "start": "Start in the background and enable logon startup",
        "stop": "Stop, disable logon startup, and turn the display off",
        "restart": "Restart and reload configuration",
        "status": "Show process, display, and background task status",
        "run": "Run in the foreground; Ctrl+C stops and turns the display off",
        "preview": "Save a synthetic PNG preview without accounts or USB",
        "uninstall-service": "Stop and remove the background task; keep configuration and logs",
    }
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description, description=description)
        if name in ("start", "restart", "run", "preview"):
            command.add_argument("--config", type=Path, help="settings TOML; defaults to the user configuration")
        if name == "status":
            command.add_argument("--json", action="store_true", help="print structured diagnostic JSON")
        if name == "preview":
            command.add_argument(
                "--output", type=Path, default=Path("auxdisp-codex-quota-preview.png"), metavar="PATH",
                help="PNG file (default: ./auxdisp-codex-quota-preview.png); replaces an existing file",
            )
    return parser


def print_status(result):
    def boolean(value):
        return "yes" if value is True else ("no" if value is False else "unknown")

    for label, key in (("Task registered", "registered"), ("Logon startup", "enabled"),
                       ("Process running", "process_running"), ("USB connected", "usb_connected"),
                       ("Health current", "health_fresh")):
        print(f"{label}: {boolean(result.get(key))}")
    print("Phase: " + (result.get("phase") or "unknown"))
    print("Last successful collection: " + (result.get("last_success_at") or "unknown"))
    stop = result.get("stop_result") or result.get("last_stop")
    if stop:
        print("Last stop screen off: " + stop.get("screen_off", "unknown"))
        print("Last stop forced: " + boolean(stop.get("forced")))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command not in ("run", "preview"):
        try:
            result = ServiceController().execute(args.command, getattr(args, "config", None))
            if args.command == "status" and args.json:
                print(json.dumps(result, ensure_ascii=True, indent=2))
            else:
                print_status(result)
            stop = result.get("stop_result", {})
            if stop.get("forced"):
                logging.warning("Managed task was forcibly stopped; display off is not confirmed")
            elif stop.get("screen_off") in ("failed", "unknown"):
                logging.warning("Process stopped; display off is not confirmed")
            return 0
        except (ServiceError, DataError, ValueError, OSError) as exc:
            logging.error("Background management failed: %s", exc)
            return 1
    try:
        settings = load_settings(select_config(args.config))
    except (ValueError, OSError) as exc:
        parser.error(f"Configuration error: {exc}")
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "preview":
        try:
            path = args.output.resolve()
            write_preview(path, settings)
            print(f"Synthetic preview saved: {path}")
            return 0
        except (ValueError, OSError, DataError):
            logging.error("Could not save preview PNG; check the output path and write permissions")
            return 1
    collector = None
    output = None
    try:
        collector = Collector(settings.executable, settings.timeout_seconds)
        output = DisplayWorker(DisplayAdapter(settings.brightness, settings.reconnect_seconds))
        runtime = Runtime(settings, CollectionWorker(collector), Renderer(settings), output)
        try:
            run_host(runtime)
        except KeyboardInterrupt:
            logging.info("Stopped; collection and display resources released")
        return 0
    except DataError as exc:
        logging.error("%s", exc)
        return 1
    except ServiceError as exc:
        logging.error("%s", exc)
        return 1
    except (ValueError, OSError):
        logging.error("Input or output could not be processed")
        return 1
    finally:
        try:
            if collector:
                collector.close()
        finally:
            if output:
                output.close()


if __name__ == "__main__":
    raise SystemExit(main())
