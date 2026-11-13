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
    unlimited = Settings(unlimited={"demo-weekly": frozenset({300})})
    images.append(renderer.render(make_page(store.snapshot, "demo-weekly", NOW, unlimited)))
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
    # Long identities must not overlap the fixed date/time region in the compact header.
    short = Renderer(Settings()).render(replace(page, title="Short"))
    assert image.crop((970, 0, 1280, 122)).tobytes() == short.crop((970, 0, 1280, 122)).tobytes()
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


def test_multiple_card_pages_cover_every_card_within_rotation(document):
    usage = document["accounts"][0]["usage"]
    usage.update(credits={"balance": "0"}, reset_credits=7, reset_credit=[
        {"title": f"Card {i}", "status": "available", "expires_at": f"2026-12-{i+1:02d}T00:00:00Z"}
        for i in reversed(range(7))
    ])
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    seen = set()
    renderer = Renderer(Settings())
    for second in range(15):
        page = make_page(store.snapshot, "demo-dual", NOW + timedelta(seconds=second), Settings())
        assert page.reset_cards == "7"
        assert len(page.cards) <= 3
        seen.update(card.title for card in page.cards)
        assert renderer.render(page).size == (1280, 720)
    assert seen == {f"Card {i} [available]" for i in range(7)}
    first = make_page(store.snapshot, "demo-dual", NOW, Settings())
    assert first.cards[0].expiry == "2026-12-01 08:00"


def test_countdowns_expired_unknown_and_quota_reset(document):
    from auxdisp_codex_quota.render import time_left
    assert time_left(None, NOW) == "--"
    assert time_left(NOW.timestamp() - 1, NOW) == "EXPIRED"
    assert time_left(NOW.timestamp(), NOW, "DUE") == "DUE"
    assert time_left(NOW.timestamp() + 1, NOW) == "1m"
    assert time_left(NOW.timestamp() + 3660, NOW) == "1h 1m"
    assert time_left(NOW.timestamp() + 90000, NOW) == "1d 1h"
    usage = document["accounts"][0]["usage"]
    usage["primary"]["resets_at"] = NOW.timestamp() + 7200
    usage["secondary"]["resets_at"] = NOW.timestamp() - 1
    usage.update(credits={}, reset_credits=1, reset_credit=[
        {"title": "Expired", "status": "expired", "expires_at": "2026-11-01T00:00:00Z"},
        {"title": "Unknown", "status": "available"},
    ])
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    page = make_page(store.snapshot, "demo-dual", NOW, Settings())
    assert page.rows[0].countdown == "2h 0m"
    assert page.rows[0].reset == "Reset 2026-11-10 22:00"
    assert page.rows[1].countdown == "DUE"
    assert [card.countdown for card in page.cards] == ["EXPIRED", "--"]


def test_only_card_region_changes_on_card_page_turn(document):
    usage = document["accounts"][0]["usage"]
    usage.update(reset_credits=4, reset_credit=[
        {"title": f"Card {i}", "status": "available", "expires_at": "2026-12-12T00:00:00Z"}
        for i in range(4)
    ])
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    renderer = Renderer(Settings())
    first = make_page(store.snapshot, "demo-dual", NOW, Settings())
    second = make_page(store.snapshot, "demo-dual", NOW + timedelta(seconds=8), Settings())
    assert first.card_page == "1/2" and second.card_page == "2/2"
    assert first.rows == second.rows and first.key == second.key
    before, after = renderer.render(first), renderer.render(second)
    assert before.crop((0, 0, 1280, 392)).tobytes() == after.crop((0, 0, 1280, 392)).tobytes()
    assert before.crop((0, 648, 1280, 720)).tobytes() == after.crop((0, 648, 1280, 720)).tobytes()
    assert before.crop((0, 392, 1280, 648)).tobytes() != after.crop((0, 392, 1280, 648)).tobytes()


def test_credit_only_update_does_not_change_visible_page(document):
    store = AccountStore()
    accounts = parse_accounts(document)
    store.success(accounts, NOW)
    before = make_page(store.snapshot, "demo-dual", NOW, Settings())
    store.success((replace(accounts[0], credits="100"),) + accounts[1:], NOW)
    assert before == make_page(store.snapshot, "demo-dual", NOW, Settings())
