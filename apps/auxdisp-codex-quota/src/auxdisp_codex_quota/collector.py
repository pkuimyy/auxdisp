"""Read-only codex-auth collection, isolated from the display scheduler."""

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import platform
from queue import Empty, Queue
import shutil
import signal
import subprocess
from threading import Event, Lock, Thread

from .model import Account, DataError, parse_accounts


LOG = logging.getLogger(__name__)


def resolve_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise DataError("COMMAND_NOT_FOUND")
    if os.name == "nt" and Path(executable).suffix.lower() in (".cmd", ".bat", ".ps1"):
        # npm's official launcher delegates to this native binary. Avoid a shell
        # so timeout/cancellation controls the actual codex-auth process tree.
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        modules = Path(executable).parent / "node_modules"
        roots = (modules / "@loongphy/codex-auth/node_modules", modules)
        native = next((root / "@loongphy" / f"codex-auth-win32-{arch}" / "bin/codex-auth.exe"
                       for root in roots
                       if (root / "@loongphy" / f"codex-auth-win32-{arch}" / "bin/codex-auth.exe").is_file()), None)
        if native is None:
            raise DataError("CONFIGURE_NATIVE_CODEX_AUTH_EXE")
        executable = str(native)
    return executable


def terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


class Collector:
    def __init__(self, executable="codex-auth", timeout=20):
        self.executable = executable
        self.timeout = timeout
        self._lock = Lock()
        self._process = None
        self._stopped = Event()

    def collect(self) -> tuple[Account, ...]:
        command = [resolve_executable(self.executable), "list", "--api", "--json"]
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        try:
            with self._lock:
                if self._stopped.is_set():
                    raise DataError("COLLECTION_STOPPED")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
                self._process = process
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                terminate_tree(process)
                process.communicate()
                raise DataError("TIMEOUT") from None
            finally:
                with self._lock:
                    self._process = None
            LOG.debug("Collector exit=%s stderr_bytes=%s", process.returncode, len(stderr))
            if process.returncode:
                raise DataError(f"COMMAND_EXIT_{process.returncode}")
            try:
                document = json.loads(stdout.decode("utf-8-sig"))
            except (ValueError, UnicodeError):
                raise DataError("INVALID_JSON") from None
            return parse_accounts(document)
        except DataError:
            raise
        except OSError:
            raise DataError("COMMAND_START_FAILED") from None

    def close(self) -> None:
        self._stopped.set()
        with self._lock:
            process = self._process
        if process is not None:
            terminate_tree(process)


@dataclass(frozen=True)
class CollectionResult:
    accounts: tuple[Account, ...] | None
    at: datetime
    error: str | None = None


class CollectionWorker:
    """At most one process and one pending result, with explicit cancellation."""

    def __init__(self, collector):
        self.collector = collector
        self.results = Queue(maxsize=1)
        self.thread = None

    def request(self) -> bool:
        if (self.thread is not None and self.thread.is_alive()) or not self.results.empty():
            return False
        self.thread = Thread(target=self._run, name="quota-collector", daemon=True)
        self.thread.start()
        return True

    def _run(self):
        try:
            accounts = self.collector.collect()
            result = CollectionResult(accounts, datetime.now().astimezone())
        except DataError as exc:
            result = CollectionResult(None, datetime.now().astimezone(), str(exc))
        except Exception:
            # Never log arbitrary subprocess content or credential-bearing exceptions.
            result = CollectionResult(None, datetime.now().astimezone(), "COLLECTION_FAILED")
        self.results.put_nowait(result)

    def take(self):
        try:
            return self.results.get_nowait()
        except Empty:
            return None

    def close(self):
        self.collector.close()
        if self.thread:
            self.thread.join(timeout=10)
