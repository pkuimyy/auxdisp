"""Read-only codex-auth collection, isolated from the display scheduler."""

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import platform
import posixpath
from queue import Empty, Queue
import shlex
import shutil
import signal
import subprocess
from threading import Event, Lock, Thread

from .model import Account, DataError, parse_accounts


LOG = logging.getLogger(__name__)

# Resolving inside WSL must survive a cold distribution start; the collection
# grace covers the same latency on top of the configured timeout.
WSL_RESOLVE_TIMEOUT = 30
WSL_LIST_TIMEOUT = 15
WSL_START_GRACE = 25


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


@dataclass(frozen=True)
class WslLaunch:
    """codex-auth location resolved inside a WSL distribution's default login shell."""

    distribution: str
    executable: str  # absolute codex-auth path inside the distribution
    node_bin: str  # directory providing node for the executable's shebang

    def __post_init__(self):
        if (not self.distribution.strip() or not self.executable.startswith("/")
                or not self.node_bin.startswith("/")):
            raise ValueError("WslLaunch requires a distribution and absolute Linux paths")


def _windowless_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def _decode_wsl_output(raw: bytes) -> str:
    # wsl.exe writes its own diagnostics (for example --list) as UTF-16LE,
    # while commands executed inside a distribution return their native bytes.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    if b"\x00" in raw[:512]:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _wsl_distributions(wsl: str) -> list[str]:
    try:
        process = subprocess.run([wsl, "--list", "--quiet"], capture_output=True,
                                  timeout=WSL_LIST_TIMEOUT, check=False, **_windowless_options())
    except (OSError, subprocess.TimeoutExpired):
        return []
    return (_decode_wsl_output(process.stdout) + "\n" + _decode_wsl_output(process.stderr)).split()


def resolve_wsl_launch(distribution: str, name: str = "codex-auth") -> WslLaunch:
    """Resolve codex-auth inside a WSL distribution using its default login shell."""
    wsl = shutil.which("wsl.exe")
    if wsl is None:
        raise DataError("WSL_NOT_INSTALLED")
    distribution = distribution.strip()
    if not distribution:
        raise DataError("WSL_DISTRO_MISSING")
    # An interactive login shell loads version managers such as nvm before PATH
    # lookups; marked output keeps bashrc noise from being mistaken for paths.
    script = (f'p=$(command -v {shlex.quote(name)}) && printf "codex:%s\\n" "$p"; '
              'n=$(command -v node) && printf "node:%s\\n" "$n"')
    try:
        process = subprocess.run(
            [wsl, "-d", distribution, "-e", "bash", "-lic", script],
            capture_output=True, timeout=WSL_RESOLVE_TIMEOUT, check=False, **_windowless_options(),
        )
    except subprocess.TimeoutExpired:
        raise DataError("WSL_RESOLVE_FAILED") from None
    except OSError:
        raise DataError("COMMAND_START_FAILED") from None
    found = {}
    for line in _decode_wsl_output(process.stdout).splitlines():
        marker, _, value = line.strip().partition(":")
        if marker in ("codex", "node") and value.startswith("/"):
            found[marker] = value
    if process.returncode or len(found) < 2:
        raise DataError("WSL_DISTRO_MISSING" if distribution not in _wsl_distributions(wsl)
                        else "WSL_RESOLVE_FAILED")
    return WslLaunch(distribution, found["codex"], posixpath.dirname(found["node"]))


def build_collector(executable: str, timeout: float, wsl_distribution: str = "") -> "Collector":
    """Resolve the configured source once, then return the matching collector."""
    if wsl_distribution:
        launch = resolve_wsl_launch(wsl_distribution, executable)
        return Collector(launch.executable, timeout, wsl=launch)
    return Collector(executable, timeout)


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
    def __init__(self, executable="codex-auth", timeout=20, wsl: WslLaunch | None = None):
        self.executable = executable
        self.timeout = timeout
        self.wsl = wsl
        self._lock = Lock()
        self._process = None
        self._stopped = Event()

    def _wsl_command(self) -> list[str]:
        wsl = shutil.which("wsl.exe")
        if wsl is None:
            raise DataError("WSL_NOT_INSTALLED")
        # The Linux-side timeout keeps expiry observable instead of orphaning
        # codex-auth when wsl.exe itself is terminated from Windows.
        environment = [f"PATH={self.wsl.node_bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
        for variable in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
            # WSL does not inherit the caller's proxy settings; forward them.
            value = os.environ.get(variable, "")
            if value:
                environment.append(f"{variable}={value}")
        # Node ignores proxy environment variables unless explicitly opted in.
        environment.append("NODE_USE_ENV_PROXY=1")
        return [wsl, "-d", self.wsl.distribution, "-e", "/usr/bin/timeout", "-k", "5",
                str(max(1, int(self.timeout))), "env", *environment,
                self.wsl.executable, "list", "--api", "--json"]

    def collect(self) -> tuple[Account, ...]:
        if self.wsl is None:
            command = [resolve_executable(self.executable), "list", "--api", "--json"]
            budget = self.timeout
        else:
            command = self._wsl_command()
            # A cold distribution start adds latency outside the Linux budget.
            budget = self.timeout + WSL_START_GRACE
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        try:
            with self._lock:
                if self._stopped.is_set():
                    raise DataError("COLLECTION_STOPPED")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
                self._process = process
            try:
                stdout, stderr = process.communicate(timeout=budget)
            except subprocess.TimeoutExpired:
                terminate_tree(process)
                process.communicate()
                raise DataError("TIMEOUT") from None
            finally:
                with self._lock:
                    self._process = None
            LOG.debug("Collector exit=%s stderr_bytes=%s", process.returncode, len(stderr))
            if process.returncode:
                # The Linux timeout helper reports its own expiry as exit status 124.
                if self.wsl is not None and process.returncode == 124:
                    raise DataError("TIMEOUT")
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
        self.thread = Thread(target=self._run, name="auxdisp-codex-quota-collector", daemon=True)
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
            if self.thread.is_alive():
                raise TimeoutError("Collection worker did not finish cancellation")
