"""Offline developer rendering tools; never opens USB or runs codex-auth."""

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from auxdisp_codex_quota.collector import CollectionWorker
from auxdisp_codex_quota.config import Settings, load_settings, positive
from auxdisp_codex_quota.display import DisplayWorker, FileAdapter
from auxdisp_codex_quota.model import AccountStore, DataError
from auxdisp_codex_quota.preview import FixtureCollector
from auxdisp_codex_quota.render import Renderer, make_page, save_preview
from auxdisp_codex_quota.runtime import Runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fixture", type=Path, help="schema-1 list JSON; defaults to bundled synthetic data")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--preview", type=Path)
    operation.add_argument("--headless", type=Path)
    operation.add_argument("--inspect", action="store_true")
    parser.add_argument("--account-index", type=int, default=0)
    parser.add_argument("--simulate-error", action="store_true")
    parser.add_argument("--duration", type=float, default=2)
    args = parser.parse_args(argv)
    if (args.simulate_error or args.account_index) and not args.preview:
        parser.error("--simulate-error and --account-index apply only to --preview")
    try:
        positive(args.duration, "duration")
        settings = load_settings(args.config) if args.config else Settings()
        collector = FixtureCollector(args.fixture)
        if args.inspect:
            print(json.dumps([asdict(account) for account in collector.collect()], indent=2, default=str))
        elif args.preview:
            accounts = collector.collect()
            if args.account_index < 0 or args.account_index >= len(accounts):
                parser.error("--account-index is outside the fixture accounts")
            now = datetime.now().astimezone()
            store = AccountStore()
            store.success(accounts, now)
            if args.simulate_error:
                store.failure("TIMEOUT")
            page = make_page(store.snapshot, accounts[args.account_index].key, now, settings, card_page_index=0)
            save_preview(Renderer(settings).render(page), args.preview)
        else:
            output = DisplayWorker(FileAdapter(args.headless))
            runtime = Runtime(settings, CollectionWorker(collector), Renderer(settings), output)
            runtime.run(args.duration)
        return 0
    except (ValueError, OSError, DataError):
        parser.error("Offline fixture, configuration, or output could not be processed")


if __name__ == "__main__":
    raise SystemExit(main())
