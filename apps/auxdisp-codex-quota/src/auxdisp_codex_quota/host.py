"""Single-instance runtime hosting, anonymous health state, and bounded file logs."""

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler
import os
import time
import uuid

from .paths import AppPaths
from .service import read_state, write_state
from .win32 import WindowsIPC


@contextmanager
def file_logging(paths, level):
    paths.log.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(paths.log, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    previous = root.level
    root.setLevel(level)
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
        handler.close()
        root.setLevel(previous)


class HealthWriter:
    def __init__(self, paths, mode):
        self.paths, self.mode = paths, mode
        self.instance = uuid.uuid4().hex
        self.last_write = float("-inf")
        self.last_success_at = read_state(paths.state).get("last_success_at")

    def update(self, runtime, phase="running", cleanup_complete=False):
        now = time.monotonic()
        if phase == "running" and now - self.last_write < 1:
            return
        self.last_write = now
        last_success = runtime.store.snapshot.last_success_at
        if last_success is not None:
            self.last_success_at = last_success.isoformat()
        write_state(self.paths.state, {
            "instance": self.instance, "pid": os.getpid(), "mode": self.mode,
            "phase": phase, "heartbeat": time.time(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "usb_connected": runtime.output.usb_connected if phase == "running" else False,
            "last_success_at": self.last_success_at,
            "cleanup_complete": cleanup_complete,
        })


def run_host(runtime, duration=None, *, paths=None, ipc=None, background=False):
    if os.name != "nt" and ipc is None:
        return runtime.run(duration)
    paths, ipc = paths or AppPaths.current(), ipc or WindowsIPC()
    claimed = False
    try:
        with ipc.lock():
            claimed = True
            # Close the log handler before releasing the instance mutex on normal exit.
            with file_logging(paths, runtime.settings.log_level) if background else nullcontext():
                try:
                    with ipc.stop_event() as stop:
                        health = HealthWriter(paths, "background" if background else "foreground")
                        if background:
                            logging.info("auxdisp-codex-quota background host starting")
                        try:
                            runtime.run(duration, stop_event=stop, on_tick=health.update)
                        except KeyboardInterrupt:
                            health.update(runtime, "stopped", cleanup_complete=True)
                            raise
                        except BaseException:
                            health.update(runtime, "failed")
                            raise
                        else:
                            health.update(runtime, "stopped", cleanup_complete=True)
                            if background:
                                logging.info("Background host stopped; collection and display resources released")
                finally:
                    try:
                        runtime.collector.close()
                    finally:
                        runtime.output.close()
    finally:
        # Also clean up workers constructed before a competing instance won the mutex.
        if not claimed:
            try:
                runtime.collector.close()
            finally:
                runtime.output.close()
