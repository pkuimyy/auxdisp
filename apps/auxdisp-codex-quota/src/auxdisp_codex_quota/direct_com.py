"""Sole task backend: bounded Python COM worker, with no fallback."""

import json
import subprocess
import sys

from .paths import APP_ID
from .task_adapter import OPERATIONS, SchedulerError, decode_response
from .win32 import current_sid


class DirectComTaskScheduler:
    def __init__(self, sid=None, runner=None, timeout=20):
        self.sid = sid or current_sid()
        self.name = f"{APP_ID}-{self.sid}"
        self.runner = runner or subprocess.run
        self.timeout = timeout

    def query(self):
        return self.call("query")

    def call(self, operation, **values):
        if operation not in OPERATIONS:
            raise SchedulerError("INVALID_OPERATION", "unknown", "request")
        try:
            result = self.runner(
                [sys.executable, "-E", "-P", "-m", "auxdisp_codex_quota._scheduler_com_worker"],
                input=json.dumps(dict(operation=operation, name=self.name, sid=self.sid, **values), ensure_ascii=True),
                capture_output=True, encoding="utf-8", errors="replace", timeout=self.timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills and reaps its own child. A service-side write
            # may already have committed; never imply that killing undoes it.
            raise SchedulerError("PROCESS_TIMEOUT", operation, "com_worker_outcome_unknown") from None
        except KeyboardInterrupt:
            raise SchedulerError("PROCESS_CANCELLED", operation, "com_worker_outcome_unknown") from None
        except OSError as exc:
            raise SchedulerError("PROCESS_START_FAILED", operation, "com_worker_start",
                                 winerror=getattr(exc, "winerror", None), errno=exc.errno) from None
        return decode_response(result, operation)
