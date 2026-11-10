from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from auxdisp_codex_quota.config import Settings, load_settings
from auxdisp_codex_quota.model import AccountStore, DataError, PageController, parse_accounts
from auxdisp_codex_quota.render import make_page, quota_style


NOW = datetime(2026, 11, 10, 20, 0, tzinfo=timezone(timedelta(hours=8)))


@pytest.mark.parametrize("used,remaining", [(100, 0), (95, 5), (8, 92), (0, 100), (-5, 100), (101, 0)])
def test_remaining_percentage_is_clamped(document, used, remaining):
    document["accounts"][0]["usage"]["primary"]["used_percent"] = used
    assert parse_accounts(document)[0].windows[0].remaining == remaining


@pytest.mark.parametrize("used", [None, "0", True, float("nan"), float("inf")])
def test_invalid_percent_is_unknown_not_zero(document, used):
    document["accounts"][0]["usage"]["primary"]["used_percent"] = used
    assert parse_accounts(document)[0].windows[0].remaining is None


def test_windows_use_duration_not_primary_secondary_position(document):
    usage = document["accounts"][0]["usage"]
    usage["primary"], usage["secondary"] = usage["secondary"], usage["primary"]
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    page = make_page(store.snapshot, "demo-dual", NOW, Settings())
    assert [row.percent for row in page.rows] == ["92%", "55%"]
    usage["primary"]["window_minutes"] = 42
    accounts = parse_accounts(document)
    assert accounts[0].windows[0].minutes == 42
    store.success(accounts, NOW)
    assert make_page(store.snapshot, "demo-dual", NOW, Settings()).rows[1].state == "UNAVAILABLE"


@pytest.mark.parametrize("document", [[], {}, {"schema_version": True}, {"schema_version": 2},
    {"schema_version": 1, "error": {"message": "private"}},
    {"schema_version": 1, "command": "switch", "accounts": []}])
def test_invalid_envelope_cannot_replace_snapshot(document):
    with pytest.raises(DataError):
        parse_accounts(document)


def test_optional_fields_and_unknown_fields_are_safe():
    result = parse_accounts({"schema_version": 1, "command": "list", "accounts": [
        {"account_key": "a", "future_field": {"ignored": 1}},
    ]})
    assert result[0].windows == ()
    assert result[0].plan == "UNKNOWN"
    with pytest.raises(FrozenInstanceError):
        result[0].plan = "changed"


def test_duplicate_or_missing_stable_key_is_rejected(document):
    document["accounts"].append(deepcopy(document["accounts"][0]))
    with pytest.raises(DataError, match="DUPLICATE"):
        parse_accounts(document)
    document["accounts"] = [{"email": "no-stable-id@example.com"}]
    with pytest.raises(DataError, match="KEY_MISSING"):
        parse_accounts(document)


def test_failure_keeps_history_and_recovery_updates_success_time(document):
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    old = store.snapshot
    store.failure("TIMEOUT")
    assert store.snapshot.accounts is old.accounts
    assert store.snapshot.last_success_at == NOW
    assert store.snapshot.error == "TIMEOUT"
    later = NOW + timedelta(minutes=1)
    store.success(parse_accounts(document), later)
    assert store.snapshot.error is None
    assert store.snapshot.last_success_at == later
    assert store.snapshot.accounts[0].last_success_at == later
    assert store.snapshot.accounts[0].updated_at != later.timestamp()


def test_partial_refresh_failure_preserves_only_failed_account(document):
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    document["accounts"][0]["usage"]["refresh"] = {"status": "http_error", "http_status": 503}
    document["accounts"][0]["usage"]["primary"]["used_percent"] = 100
    document["accounts"][1]["usage"]["primary"]["used_percent"] = 50
    store.success(parse_accounts(document), NOW + timedelta(minutes=1))
    assert store.snapshot.accounts[0].windows[0].remaining == 92
    assert store.snapshot.accounts[0].last_success_at == NOW
    assert store.snapshot.accounts[1].windows[0].remaining == 50
    failed = make_page(store.snapshot, "demo-dual", NOW, Settings())
    fresh = make_page(store.snapshot, "demo-weekly", NOW, Settings())
    assert failed.status == "API ERROR" and "STALE" in failed.detail and "503" in failed.detail
    assert fresh.status == "API OK" and not fresh.stale


def test_removed_accounts_do_not_survive_successful_empty_list(document):
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    store.success((), NOW)
    assert store.snapshot.accounts == ()


def test_unlimited_policy_requires_exact_stable_key(document):
    store = AccountStore()
    store.success(parse_accounts(document), NOW)
    settings = Settings(unlimited={"demo-weekly": frozenset({300})})
    assert make_page(store.snapshot, "demo-weekly", NOW, Settings()).rows[0].state == "UNAVAILABLE"
    assert make_page(store.snapshot, "demo-weekly", NOW, settings).rows[0].state == "NOT LIMITED"
    assert make_page(store.snapshot, "demo-dual", NOW, settings).rows[0].state == "known"


@pytest.mark.parametrize("remaining,count,index", [(0, 0, 3), (1, 1, 3), (10, 1, 3), (11, 2, 3),
    (25, 3, 2), (50, 5, 1), (75, 8, 0), (92, 10, 0), (100, 10, 0)])
def test_bar_counts_and_color_boundaries(remaining, count, index):
    from auxdisp_codex_quota.render import COLORS
    assert quota_style(remaining) == (count, COLORS[index])


def test_account_reordering_does_not_reset_rotation_deadline(document):
    accounts = parse_accounts(document)
    pages = PageController(15)
    pages.update(accounts, 0)
    pages.update(tuple(reversed(accounts)), 10)
    assert pages.current == "demo-dual" and pages.deadline == 15
    pages.tick(15)
    assert pages.current == "demo-low"
    pages.update((accounts[0], accounts[1]), 16)
    assert pages.current == "demo-weekly"
    pages.update((), 17)
    assert pages.current is None
    pages.update((accounts[0],), 18)
    pages.tick(100)
    assert pages.current == "demo-dual"


def test_five_accounts_rotate_without_fixed_account_count(document):
    document["accounts"] = [dict(document["accounts"][0], account_key=str(i)) for i in range(5)]
    pages = PageController(15)
    pages.update(parse_accounts(document), 0)
    seen = []
    for now in range(0, 90, 15):
        pages.tick(now)
        seen.append(pages.current)
    assert seen == ["0", "1", "2", "3", "4", "0"]


@pytest.mark.parametrize("body", [
    "[collector]\nrefresh_seconds=0", "[collector]\ntimeout_seconds=nan",
    "[rotation]\nseconds=-1", "[display]\nbrightness=101", "[display]\nbrightness=true",
    '[display]\norientation="portrait"', '[render]\nthresholds=[25,50,75]',
    '[accounts.a]\nunlimited_windows=[42]', '[logging]\nlevel="unknown"',
])
def test_invalid_configuration_fails_early(tmp_path, body):
    path = tmp_path / "settings.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(path)


def test_example_configuration_loads_and_has_safe_defaults():
    from pathlib import Path
    settings = load_settings(Path(__file__).parents[1] / "config.example.toml")
    assert (settings.refresh_seconds, settings.rotation_seconds, settings.timeout_seconds) == (60, 15, 20)
    assert settings.brightness == 30
