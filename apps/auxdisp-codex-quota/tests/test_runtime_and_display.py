from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
import time
from unittest.mock import Mock

from PIL import Image

from auxdisp_codex_quota.collector import CollectionResult
from auxdisp_codex_quota.config import Settings
from auxdisp_codex_quota.display import DisplayAdapter, DisplayWorker
from auxdisp_codex_quota.model import parse_accounts
from auxdisp_codex_quota.runtime import Runtime


NOW = datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc)


class FakeCollection:
    def __init__(self, result):
        self.result = result
        self.requests = 0
        self.busy = False

    def take(self):
        value, self.result = self.result, None
        return value

    def request(self):
        if self.busy:
            return False
        self.requests += 1
        self.busy = True
        return True

    def close(self):
        pass


def test_collection_rotation_and_clock_are_independent_and_deduplicated(document):
    accounts = parse_accounts(document)
    collector = FakeCollection(CollectionResult(accounts, NOW))
    renderer, output = Mock(), Mock()
    runtime = Runtime(Settings(), collector, renderer, output)
    runtime.step(0, NOW)
    history = runtime.store.snapshot.accounts
    assert runtime.pages.current == "demo-dual"
    for i in range(1, 15):
        runtime.step(i, NOW + timedelta(seconds=i))
    assert renderer.render.call_count == 1
    assert collector.requests == 1
    runtime.step(15, NOW + timedelta(seconds=15))
    assert runtime.pages.current == "demo-weekly"
    assert renderer.render.call_count == 2
    # The API is still blocked, but the clock advances and pages keep rotating.
    runtime.step(60, NOW + timedelta(minutes=1))
    assert renderer.render.call_args.args[0].clock == "20:01"
    assert collector.requests == 1
    collector.busy = False
    collector.result = CollectionResult(None, NOW, "TIMEOUT")
    runtime.step(61, NOW + timedelta(minutes=1, seconds=1))
    assert collector.requests == 2
    assert runtime.store.snapshot.accounts is history
    assert renderer.render.call_args.args[0].status == "API ERROR"
    assert runtime.pages.deadline == 75
    collector.busy = False
    collector.result = CollectionResult(accounts, NOW + timedelta(minutes=1))
    runtime.step(62, NOW + timedelta(minutes=1, seconds=2))
    assert renderer.render.call_args.args[0].status == "API OK"
    assert runtime.pages.deadline == 75


def test_invisible_account_change_does_not_send_a_frame(document):
    accounts = parse_accounts(document)
    collector = FakeCollection(CollectionResult(accounts, NOW))
    renderer, output = Mock(), Mock()
    runtime = Runtime(Settings(), collector, renderer, output)
    runtime.step(0, NOW)
    updated = accounts[:1] + (replace(accounts[1], alias="Changed off screen"),) + accounts[2:]
    collector.result = CollectionResult(updated, NOW)
    runtime.step(1, NOW + timedelta(seconds=1))
    assert output.submit.call_count == 1


def test_usb_errors_retry_and_force_the_same_frame_after_reconnect():
    broken, recovered = Mock(), Mock()
    broken.show.side_effect = OSError("unplugged")
    opener = Mock(side_effect=[broken, OSError("not connected"), recovered])
    adapter = DisplayAdapter(reconnect_seconds=5, opener=opener)
    image = Image.new("RGB", (10, 10))
    assert not adapter.send(image, "same", 0)
    broken.close.assert_called_once()
    assert not adapter.send(image, "same", 4)
    assert opener.call_count == 1
    assert not adapter.send(image, "same", 5)
    assert adapter.send(image, "same", 10)
    assert adapter.send(image, "same", 11)
    recovered.show.assert_called_once_with(image)
    adapter.close()
    recovered.close.assert_called_once()


def test_display_worker_keeps_latest_frame_without_unbounded_queue():
    entered, release, delivered = Event(), Event(), Event()

    class SlowDisplay:
        def __init__(self):
            self.seen = []
            self.closed = False

        def send(self, image, signature, now):
            if not self.seen:
                entered.set()
                release.wait(3)
            if not self.seen or self.seen[-1] != signature:
                self.seen.append(signature)
            if signature == "last":
                delivered.set()
            return True

        def close(self):
            self.closed = True

    adapter = SlowDisplay()
    output = DisplayWorker(adapter)
    image = Image.new("RGB", (1, 1))
    try:
        output.submit(image, "first")
        assert entered.wait(1)
        for i in range(100):
            output.submit(image, str(i))
        output.submit(image, "last")
        release.set()
        assert delivered.wait(2)
    finally:
        release.set()
        output.close()
    assert adapter.seen == ["first", "last"]
    assert adapter.closed and not output.thread.is_alive()


def test_reconnect_worker_keeps_retrying_without_new_submissions():
    device = Mock()
    opener = Mock(side_effect=[OSError("unplugged"), device])
    output = DisplayWorker(DisplayAdapter(reconnect_seconds=0.05, opener=opener))
    try:
        output.submit(Image.new("RGB", (1, 1)), "static")
        deadline = time.monotonic() + 2
        while not device.show.called and time.monotonic() < deadline:
            time.sleep(0.02)
        assert device.show.call_count == 1
    finally:
        output.close()
    device.close.assert_called_once()
