"""Latest-frame-only USB delivery and reconnect, on its own worker thread."""

import logging
from pathlib import Path
from threading import Event, Lock, Thread
import time

from PIL import Image


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
        self.closed = False
        self.screen_off_result = "not_attempted"

    def send(self, image, signature, now):
        if self.closed:
            return False
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
            self._release()
            self.retry_at = now + self.reconnect_seconds
            LOG.warning("USB transfer failed; reconnect scheduled")
            return False

    def _release(self):
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                LOG.warning("USB cleanup failed")
            finally:
                self.device = None
                self.sent = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.device is None:
            return
        failed = False
        # Use the public auxdisp-driver API on the output thread. Both actions
        # are attempted independently, even if the transport fails on one.
        try:
            self.device.show(Image.new("RGB", (self.device.width, self.device.height), "black"))
        except Exception:
            failed = True
            LOG.warning("Screen clear failed during shutdown")
        try:
            self.device.set_brightness(0)
        except Exception:
            failed = True
            LOG.warning("Screen brightness reset failed during shutdown")
        finally:
            self.screen_off_result = "failed" if failed else "succeeded"
            self._release()
        LOG.info("Screen off on shutdown: %s", self.screen_off_result)


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
            if self._stop.is_set():
                return
            self._desired = (image.copy(), signature)
        self._wake.set()

    @property
    def usb_connected(self):
        # Last observed transport state; headless output has no USB connection.
        return self.adapter.device is not None if isinstance(self.adapter, DisplayAdapter) else None

    @property
    def screen_off_result(self):
        return self.adapter.screen_off_result if isinstance(self.adapter, DisplayAdapter) else "not_attempted"

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
        with self._lock:
            self._stop.set()
            self._desired = None
        self._wake.set()
        # The controller's stop deadline handles a genuinely wedged OS USB call.
        # Keep the instance lock until the adapter has actually released resources.
        self.thread.join()
