from copy import deepcopy
from importlib.resources import files
import json

import pytest


@pytest.fixture
def document():
    return deepcopy(json.loads(files("auxdisp_codex_quota").joinpath("data/demo.json").read_text(encoding="utf-8")))
