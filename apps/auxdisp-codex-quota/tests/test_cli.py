"""Public command contracts and side-effect-free PNG previews."""

from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import Mock
import webbrowser

from PIL import Image
import pytest

from auxdisp_codex_quota import cli
from auxdisp_codex_quota.config import Settings
from auxdisp_codex_quota.model import AccountStore, parse_accounts
from auxdisp_codex_quota.preview import write_preview
from auxdisp_codex_quota.render import Renderer, make_page, save_preview


def forbid_runtime(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Preview/help must not use accounts, USB, tasks, or a browser")

    for name in ("Collector", "CollectionWorker", "DisplayAdapter", "DisplayWorker", "ServiceController", "run_host"):
        monkeypatch.setattr(cli, name, fail)
    monkeypatch.setattr(webbrowser, "open", fail)


def test_no_arguments_print_help_without_side_effects(monkeypatch, capsys):
    forbid_runtime(monkeypatch)
    assert cli.main([]) == 0
    help_text = capsys.readouterr().out
    assert "preview" in help_text and "start" in help_text
    assert "--fixture" not in help_text and "--duration" not in help_text


@pytest.mark.parametrize("arguments", [
    ["--preview", "x.png"], ["run", "--demo"], ["run", "--headless", "x.png"],
    ["run", "--duration", "1"], ["preview", "--fixture", "x.json"], ["preview", "--account-index", "1"],
    ["preview", "--simulate-error"], ["--inspect"], ["stop", "--config", "x.toml"],
    ["start", "--json"], ["--config", "x.toml", "run"],
])
def test_invalid_or_developer_parameters_rejected_before_actions(arguments, monkeypatch):
    forbid_runtime(monkeypatch)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize("command", ["start", "stop", "restart", "status", "run", "preview", "uninstall-service"])
def test_each_command_has_local_help(command, monkeypatch, capsys):
    forbid_runtime(monkeypatch)
    with pytest.raises(SystemExit) as error:
        cli.main([command, "--help"])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert command in output and "--demo" not in output
    assert ("--config" in output) == (command in ("start", "restart", "run", "preview"))


def test_default_preview_uses_current_directory_and_replaces_existing_png(tmp_path, monkeypatch, capsys):
    forbid_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "auxdisp-codex-quota-preview.png"
    path.write_bytes(b"old generated preview")
    assert cli.main(["preview"]) == 0
    with Image.open(path) as image:
        assert image.format == "PNG" and image.size == (1280, 720)
    assert "Synthetic preview" in capsys.readouterr().out
    assert not list(tmp_path.glob(".auxdisp-codex-quota-*"))


@pytest.mark.parametrize("absolute", [False, True])
def test_preview_explicit_paths_and_configuration(tmp_path, monkeypatch, absolute, capsys):
    forbid_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "render.toml"
    config.write_text('[render]\nthresholds = [80, 60, 40]\n', encoding="utf-8")
    relative = Path("new/preview.png")
    output = tmp_path / relative if absolute else relative
    assert cli.main(["preview", "--config", str(config), "--output", str(output)]) == 0
    assert (tmp_path / relative).is_file()
    assert str((tmp_path / relative).resolve()) in capsys.readouterr().out


def test_preview_failure_returns_nonzero_and_preserves_old_file(tmp_path, monkeypatch, caplog):
    forbid_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "auxdisp-codex-quota-preview.png"
    path.write_bytes(b"old")

    def failed_save(self, target, **kwargs):
        target.write(b"partial")
        raise OSError("write failed")

    monkeypatch.setattr(Image.Image, "save", failed_save)
    assert cli.main(["preview"]) == 1
    assert path.read_bytes() == b"old"
    assert "Could not save preview PNG" in caplog.text
    assert not list(tmp_path.glob(".auxdisp-codex-quota-*"))


def test_preview_starts_at_first_card_page_even_late_in_rotation(tmp_path, document, monkeypatch):
    usage = document["accounts"][0]["usage"]
    usage["reset_credit"] *= 3
    accounts = parse_accounts(document)
    monkeypatch.setattr("auxdisp_codex_quota.preview.FixtureCollector.collect", lambda self: accounts)
    now = datetime(2026, 11, 10, 20, 0, 14, tzinfo=timezone.utc)
    path = tmp_path / "preview.png"
    write_preview(path, Settings(), now=now)
    store = AccountStore()
    store.success(accounts, now)
    expected = Renderer(Settings()).render(make_page(store.snapshot, accounts[0].key, now, Settings(), card_page_index=0))
    assert Image.open(path).tobytes() == expected.tobytes()
    assert make_page(store.snapshot, accounts[0].key, now, Settings()).card_page == "2/2"


def test_preview_replacement_failure_preserves_old_file(tmp_path, monkeypatch):
    path = tmp_path / "preview.png"
    path.write_bytes(b"old")
    monkeypatch.setattr(Path, "replace", Mock(side_effect=PermissionError("locked")))
    with pytest.raises(PermissionError):
        save_preview(Image.new("RGB", (1, 1)), path)
    assert path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".auxdisp-codex-quota-*"))


def test_status_text_and_json_distinguish_unknown_usb(monkeypatch, capsys):
    state = {"registered": True, "enabled": False, "process_running": False, "usb_connected": None,
             "health_fresh": False, "phase": "stopped", "last_stop": {"screen_off": "unknown", "forced": True}}
    controller = Mock()
    controller.execute.return_value = state
    monkeypatch.setattr(cli, "ServiceController", lambda: controller)
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    assert "USB connected: unknown" in output and "Last stop forced: yes" in output
    assert cli.main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == state


def test_foreground_ctrl_c_is_handled_and_resources_closed(monkeypatch):
    collector, runtime, output = Mock(), Mock(), Mock()
    monkeypatch.setattr(cli, "Collector", Mock(return_value=collector))
    monkeypatch.setattr(cli, "CollectionWorker", Mock())
    monkeypatch.setattr(cli, "DisplayWorker", Mock(return_value=output))
    monkeypatch.setattr(cli, "DisplayAdapter", Mock())
    monkeypatch.setattr(cli, "Runtime", Mock(return_value=runtime))
    monkeypatch.setattr(cli, "run_host", Mock(side_effect=KeyboardInterrupt))
    assert cli.main(["run"]) == 0
    collector.close.assert_called_once()
