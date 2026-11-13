"""Synthetic data and a single offline PNG, with no runtime or device access."""

from datetime import datetime
from importlib.resources import files
import json

from .model import AccountStore, parse_accounts
from .render import Renderer, make_page, save_preview


class FixtureCollector:
    def __init__(self, path=None):
        data = (path.read_text(encoding="utf-8") if path else
                files("auxdisp_codex_quota").joinpath("data/demo.json").read_text(encoding="utf-8"))
        self.accounts = parse_accounts(json.loads(data))

    def collect(self):
        return self.accounts

    def close(self):
        pass


def write_preview(path, settings, *, now=None):
    now = now or datetime.now().astimezone()
    accounts = FixtureCollector().collect()
    store = AccountStore()
    store.success(accounts, now)
    key = accounts[0].key if accounts else None
    page = make_page(store.snapshot, key, now, settings, card_page_index=0)
    save_preview(Renderer(settings).render(page), path)
