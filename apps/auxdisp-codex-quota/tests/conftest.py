from copy import deepcopy
from importlib.resources import files
import json
import uuid

import pytest

from auxdisp_codex_quota.win32 import WindowsIPC


@pytest.fixture(autouse=True)
def isolated_application_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state-home"))
    namespace = "pytest-" + uuid.uuid4().hex
    monkeypatch.setattr("auxdisp_codex_quota.host.WindowsIPC", lambda: WindowsIPC(namespace))


@pytest.fixture
def document():
    return deepcopy(json.loads(files("auxdisp_codex_quota").joinpath("data/demo.json").read_text(encoding="utf-8")))
