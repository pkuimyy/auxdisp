"""Latest-frame-only USB delivery and reconnect, on its own worker thread."""

import logging
from pathlib import Path
from threading import Event, Lock, Thread
import time


LOG = logging.getLogger(__name__)


def open_turing(brightness):
    from auxdisp_driver import Orientation, open_display

    display = open_display("turing_usb", orientation=Orientation.LANDSCAPE)
    try:
        if display.device.dev_pid != 0x0050 or (display.width, display.height) != (1280, 720):
            raise RuntimeError("Expected Turing USB 5.2 inch 1280x720")
        display.set_brightness(brightness)
        return display
    except Exception:
        display.close()
        raise


class DisplayAdapter:
    def __init__(self, brightness=30, reconnect_seconds=5, opener=None):
        self.opener = opener or (lambda: open_turing(brightness))
        self.reconnect_seconds = reconnect_seconds
        self.device = None
        self.retry_at = 0.0
        self.sent = None

    def send(self, image, signature, now):
        if self.device is None:
            if now < self.retry_at:
                return False
            try:
                self.device = self.opener()
                self.sent = None
                LOG.info("USB connected")
            except Exception:
                self.retry_at = now + self.reconnect_seconds
                LOG.warning("USB unavailable; reconnect scheduled")
                return False
        if signature == self.sent:
            return True
        try:
            started = time.monotonic()
            self.device.show(image)
            self.sent = signature
            LOG.info("USB full-frame send %.3fs", time.monotonic() - started)
            return True
        except Exception:
            self.close()
            self.retry_at = now + self.reconnect_seconds
            LOG.warning("USB transfer failed; reconnect scheduled")
            return False

    def close(self):
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                LOG.warning("USB cleanup failed")
            finally:
                self.device = None
                self.sent = None


class FileAdapter:
    def __init__(self, path: Path):
        self.path = path
        self.sent = None

    def send(self, image, signature, now):
        if signature != self.sent:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp.png")
            image.save(temporary, format="PNG")
            temporary.replace(self.path)
            self.sent = signature
        return True

    def close(self):
        pass


class DisplayWorker:
    """A single desired frame replaces the previous one instead of queuing."""

    def __init__(self, adapter):
        self.adapter = adapter
        self._lock = Lock()
        self._wake = Event()
        self._stop = Event()
        self._desired = None
        self.thread = Thread(target=self._run, name="auxdisp-codex-quota-display", daemon=True)
        self.thread.start()

    def submit(self, image, signature):
        with self._lock:
            self._desired = (image.copy(), signature)
        self._wake.set()

    def _run(self):
        try:
            while not self._stop.is_set():
                self._wake.clear()
                with self._lock:
                    desired = self._desired
                if desired is not None:
                    try:
                        self.adapter.send(*desired, time.monotonic())
                    except Exception:
                        LOG.warning("Frame output failed")
                self._wake.wait(0.25)
        finally:
            self.adapter.close()

    def close(self):
        self._stop.set()
        self._wake.set()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            LOG.warning("Waiting for USB operation to finish before cleanup")
