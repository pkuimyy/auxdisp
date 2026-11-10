from dataclasses import replace
from datetime import datetime, timedelta, timezone

from PIL import Image

from auxdisp_codex_quota.cli import main
from auxdisp_codex_quota.config import Settings
from auxdisp_codex_quota.model import AccountStore, parse_accounts
from auxdisp_codex_quota.render import BG, MUTED, Renderer, make_page


NOW = datetime(2026, 11, 10, 20, 0, tzinfo=timezone(timedelta(hours=8)))


def test_clock_position_is_identical_for_normal_single_missing_and_error_pages(document):
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    renderer = Renderer(Settings())
    images = []
    for account in store.snapshot.accounts:
        image = renderer.render(make_page(store.snapshot, account.key, NOW, Settings()))
        assert image.size == (1280, 720) and image.mode == "RGB"
        images.append(image)
    store.failure("TIMEOUT")
    images.append(renderer.render(make_page(store.snapshot, "demo-dual", NOW, Settings())))
    store.success((), NOW)
    images.append(renderer.render(make_page(store.snapshot, None, NOW, Settings())))
    clock = images[0].crop((970, 0, 1280, 145)).tobytes()
    assert all(image.crop((970, 0, 1280, 145)).tobytes() == clock for image in images)


def test_unknown_is_not_zero_and_long_unicode_title_is_clipped(document):
    store = AccountStore()
    accounts = parse_accounts(document)
    store.success((replace(accounts[1], alias="很长的账户名称" * 100),), NOW)
    page = make_page(store.snapshot, "demo-weekly", NOW, Settings())
    assert page.rows[0].state == "UNAVAILABLE" and page.rows[0].color == MUTED
    image = Renderer(Settings()).render(page)
    assert image.getpixel((1279, 200)) == tuple(int(BG[i:i+2], 16) for i in (1, 3, 5))
    store.success((accounts[2],), NOW)
    page = make_page(store.snapshot, "demo-low", NOW, Settings())
    assert page.rows[1].state == "known" and page.rows[1].percent == "0%"


def test_preview_modes_never_start_collector_or_usb(tmp_path, monkeypatch):
    monkeypatch.setattr("auxdisp_codex_quota.cli.Collector", lambda *a: (_ for _ in ()).throw(AssertionError("API called")))
    monkeypatch.setattr("auxdisp_codex_quota.cli.DisplayWorker", lambda *a: (_ for _ in ()).throw(AssertionError("USB called")))
    for name, options in (("dual", []), ("single", ["--account-index", "1"]), ("error", ["--simulate-error"])):
        path = tmp_path / f"{name}.png"
        assert main(["--preview", str(path), *options]) == 0
        with Image.open(path) as image:
            assert image.size == (1280, 720)


def test_headless_demo_stops_and_releases_workers(tmp_path):
    output = tmp_path / "latest.png"
    assert main(["--demo", "--headless", str(output), "--duration", "0.6"]) == 0
    assert output.is_file()


def test_unknown_window_is_retained_but_does_not_appear_as_weekly(document):
    document["accounts"][0]["usage"]["secondary"]["window_minutes"] = 60
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    page = make_page(store.snapshot, "demo-dual", NOW, Settings())
    assert page.rows[1].state == "UNAVAILABLE"
    assert store.snapshot.accounts[0].windows[1].minutes == 60
