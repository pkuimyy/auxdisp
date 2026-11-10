"""CLI entry points for live display, offline previews, and safe inspection."""

import argparse
from dataclasses import asdict
from datetime import datetime
from importlib.resources import files
import json
import logging
from pathlib import Path

from .collector import CollectionWorker, Collector
from .config import load_settings, positive
from .display import DisplayAdapter, DisplayWorker, FileAdapter
from .host import run_host
from .model import AccountStore, DataError, parse_accounts
from .render import Renderer, make_page, save_preview
from .runtime import Runtime
from .paths import select_config
from .service import ServiceController
from .win32 import ServiceError


class FixtureCollector:
    def __init__(self, path=None):
        data = path.read_text(encoding="utf-8") if path else files("auxdisp_codex_quota").joinpath("data/demo.json").read_text(encoding="utf-8")
        self.accounts = parse_accounts(json.loads(data))

    def collect(self):
        return self.accounts

    def close(self):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="auxdisp-codex-quota", description="Codex account quotas on a Turing USB 5.2-inch display",
    )
    parser.add_argument("command", nargs="?", default="run",
                        choices=("start", "stop", "status", "restart", "run", "uninstall-service"),
                        help="foreground run (default) or current-user Windows background task management")
    parser.add_argument("--config", type=Path, help="settings TOML; defaults to the current user's app data directory")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--demo", action="store_true", help="use bundled synthetic accounts instead of codex-auth")
    source.add_argument("--fixture", type=Path, help="use a schema-1 list document instead of codex-auth")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--preview", type=Path, help="write one offline PNG; defaults to synthetic data")
    operation.add_argument("--inspect", action="store_true", help="print normalized account data without USB access")
    parser.add_argument("--account-index", type=int, default=0, help="zero-based preview account index")
    parser.add_argument("--simulate-error", action="store_true", help="preview a timeout with retained historical data")
    parser.add_argument("--headless", type=Path, help="write the latest page to PNG instead of accessing USB")
    parser.add_argument("--duration", type=float, help="stop a test run after this many seconds")
    args = parser.parse_args(argv)
    if args.command != "run":
        if (args.demo or args.fixture or args.preview or args.inspect or args.headless
                or args.duration is not None or args.simulate_error or args.account_index):
            parser.error("Preview, collection, and output options require run")
        if args.config and args.command not in ("start", "restart"):
            parser.error("--config applies to start, restart, or run")
        try:
            result = ServiceController().execute(args.command, args.config)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            if result.get("stop_result", {}).get("forced"):
                logging.warning("Managed task was forcibly stopped after the graceful-stop timeout")
            return 0
        except (ServiceError, DataError, ValueError, OSError) as exc:
            # Task/collector errors are deliberately safe codes, never raw subprocess output.
            logging.error("Background management failed: %s", exc)
            return 1
    if args.simulate_error and not args.preview:
        parser.error("--simulate-error requires --preview")
    if args.headless and (args.preview or args.inspect):
        parser.error("--headless is a live-output option")
    if args.duration is not None:
        try:
            positive(args.duration, "duration")
        except ValueError as exc:
            parser.error(str(exc))
    try:
        config = select_config(args.config)
        settings = load_settings(config)
    except (ValueError, OSError) as exc:
        parser.error(f"Configuration error: {exc}")
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    collector = None
    try:
        collector = (FixtureCollector(args.fixture) if args.demo or args.fixture or args.preview
                     else Collector(settings.executable, settings.timeout_seconds))
        if args.inspect or args.preview:
            accounts = collector.collect()
            if args.inspect:
                print(json.dumps([asdict(account) for account in accounts], ensure_ascii=False, indent=2, default=str))
                return 0
            if args.account_index < 0 or (accounts and args.account_index >= len(accounts)):
                parser.error("--account-index is outside the available accounts")
            store = AccountStore()
            now = datetime.now().astimezone()
            store.success(accounts, now)
            if args.simulate_error:
                store.failure("TIMEOUT")
            key = accounts[args.account_index].key if accounts else None
            image = Renderer(settings).render(make_page(store.snapshot, key, now, settings))
            save_preview(image, args.preview)
            logging.info("Offline preview written: %s", args.preview)
            return 0
        output = DisplayWorker(FileAdapter(args.headless) if args.headless else DisplayAdapter(
            settings.brightness, settings.reconnect_seconds,
        ))
        runtime = Runtime(settings, CollectionWorker(collector), Renderer(settings), output)
        try:
            run_host(runtime, args.duration)
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
        if collector:
            collector.close()


if __name__ == "__main__":
    raise SystemExit(main())
