"""Read-only experiment coverage; no PowerShell, registration, or task scans."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest


spec = importlib.util.spec_from_file_location("com_probe", Path(__file__).parents[1] / "scripts/probe_task_scheduler_com.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


@pytest.mark.parametrize("identity,marker,count,arguments,error", [
    ("sid", True, 1, experiment.PREFIXES[0] + "test", None),
    ("username", True, 1, experiment.PREFIXES[1] + "test", None),
    ("DOMAIN\\username", True, 1, experiment.PREFIXES[0] + "test", None),
    ("other", True, 1, experiment.PREFIXES[0] + "test", "TASK_IDENTITY_MISMATCH"),
    ("unresolved", True, 1, experiment.PREFIXES[0] + "test", "TASK_IDENTITY_UNRESOLVED"),
    ("sid", False, 1, experiment.PREFIXES[0] + "test", "TASK_MARKER_MISMATCH"),
    ("sid", True, 2, experiment.PREFIXES[0] + "test", "TASK_ACTION_MISMATCH"),
    ("sid", True, 1, "-I -m unrelated test", "TASK_ACTION_MISMATCH"),
])
def test_probe_only_reads_expected_owned_task(identity, marker, count, arguments, error):
    sid = "S-1-5-21-test"
    actions = SimpleNamespace(Count=count, Item=Mock(return_value=SimpleNamespace(Arguments=arguments)))
    task = SimpleNamespace(Name="auxdisp-codex-quota-" + sid, Definition=SimpleNamespace(
        Principal=SimpleNamespace(UserId=identity), Actions=actions,
        RegistrationInfo=SimpleNamespace(Description=experiment.MARKER + "hash" if marker else "unrelated"),
    ))
    folder = SimpleNamespace(GetTask=Mock(return_value=task))  # No mutation or enumeration methods exist.
    service = SimpleNamespace(Connect=Mock(), GetFolder=Mock(return_value=folder))

    def resolve(value):
        if value == "unresolved":
            raise ValueError("PRIVATE identity")
        return "other sid" if value == "other" else sid

    result = experiment.probe(lambda: service, sid, resolve)
    assert result["status"] == ("REFUSED" if error else "OK")
    assert result.get("error") == error
    folder.GetTask.assert_called_once_with("auxdisp-codex-quota-" + sid)
    service.GetFolder.assert_called_once_with("\\")
    assert "PRIVATE" not in str(result)


@pytest.mark.parametrize("code,error,status", [
    (0x80070005, "ACCESS_DENIED", "FAILED"),
    (0x800706BA, "COM_PROBE_FAILED", "FAILED"),
    (0x80070002, None, "OK"),
    (0x8004130F, None, "OK"),
])
def test_probe_keeps_hresult_and_does_not_retry(code, error, status):
    exc = RuntimeError("PRIVATE path and credentials")
    exc.hresult = code
    folder = SimpleNamespace(GetTask=Mock(side_effect=exc))
    service = SimpleNamespace(Connect=Mock(), GetFolder=Mock(return_value=folder))
    result = experiment.probe(lambda: service, "test", lambda identity: identity)
    assert result["status"] == status and result.get("error") == error
    assert result["stage"] == "get_task" and folder.GetTask.call_count == 1
    assert "PRIVATE" not in str(result)


@pytest.mark.skipif(os.name != "nt", reason="Native account lookup requires Windows")
def test_native_sid_name_and_qualified_name_resolution():
    security = pytest.importorskip("win32security", reason="Optional experiment dependency")
    from auxdisp_codex_quota.win32 import current_sid

    sid = current_sid()
    name, domain, _ = security.LookupAccountSid(None, security.ConvertStringSidToSid(sid))
    for identity in (sid, name, domain + "\\" + name):
        assert experiment.resolve_identity(identity, security) == sid
    assert experiment.resolve_identity("S-1-5-18", security) != sid
    with pytest.raises(Exception):
        experiment.resolve_identity("auxdisp-no-such-user-" + uuid.uuid4().hex, security)
