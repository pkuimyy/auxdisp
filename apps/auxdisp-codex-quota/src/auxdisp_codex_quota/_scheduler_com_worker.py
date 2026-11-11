"""One Task Scheduler COM operation per isolated Python process."""

import json
import re
import sys
from xml.etree import ElementTree as ET

from .paths import APP_ID
from .task_adapter import OPERATIONS, SchedulerError, validate_ownership
from .task_spec import NS


MISSING = {0x80070002, 0x8004130F}


def com_codes(exc):
    values = {}
    if type(getattr(exc, "hresult", None)) is int:
        values["code"] = exc.hresult & 0xFFFFFFFF
    info = getattr(exc, "excepinfo", None)
    if isinstance(info, tuple) and len(info) > 5 and type(info[5]) is int:
        values["scode"] = info[5] & 0xFFFFFFFF
    return values


def resolve_identity(identity, security):
    value = (security.ConvertStringSidToSid(identity) if identity.upper().startswith("S-")
             else security.LookupAccountName(None, identity)[0])
    return security.ConvertSidToStringSid(value)


def validate_definition(definition, sid, resolve):
    actions = definition.Actions
    count = actions.Count
    validate_ownership(definition.Principal.UserId, definition.RegistrationInfo.Description,
                       count, actions.Item(1).Arguments if count == 1 else None, sid, resolve)


def execute_operation(request, create_service, resolve):
    """Injectable COM boundary; all snapshots are plain JSON-compatible data."""
    stage = "create_com"
    service = folder = task = candidate = None
    try:
        operation, name, sid = request["operation"], request["name"], request["sid"]
        if operation not in OPERATIONS or not re.fullmatch(re.escape(f"{APP_ID}-{sid}") + r"(?:-[A-Za-z0-9-]+)?", name):
            return {"error": "INVALID_REQUEST"}
        service = create_service()
        stage = "connect"
        service.Connect()
        stage = "get_root"
        folder = service.GetFolder("\\")
        stage = "get_task"
        try:
            task = folder.GetTask(name)
        except Exception as exc:
            if not MISSING.intersection(com_codes(exc).values()):
                raise
        stage = "ownership"
        if task is not None:
            validate_definition(task.Definition, sid, resolve)
        if operation == "query":
            if task is None:
                return {"registered": False}
            return {"registered": True, "enabled": bool(task.Enabled), "state": int(task.State),
                    "last_result": int(task.LastTaskResult), "description": task.Definition.RegistrationInfo.Description,
                    "python": task.Definition.Actions.Item(1).Path, "xml": task.Xml}
        if operation == "register":
            stage = "validate_spec"
            xml = request["xml"]
            root = ET.fromstring(xml)
            if root.findtext(f"{{{NS}}}Settings/{{{NS}}}Enabled") != "false":
                return {"error": "INVALID_TASK_SPEC"}
            candidate = service.NewTask(0)
            candidate.XmlText = xml
            validate_definition(candidate, sid, resolve)
            stage = "task_operation"
            folder.RegisterTask(name, xml, 6, sid, None, 3, None)
        elif operation in ("enable", "disable"):
            if task is not None:
                stage = "task_operation"
                task.Enabled = operation == "enable"
        elif operation == "run":
            if task is None:
                return {"error": "INVALID_TASK_SPEC"}
            stage = "task_operation"
            task.Run(None)
        elif operation == "end":
            if task is not None:
                stage = "task_operation"
                task.Stop(0)
        elif operation == "delete":
            if task is not None:
                stage = "task_operation"
                folder.DeleteTask(name, 0)
        return {}
    except SchedulerError as exc:
        return {"error": exc.kind, "stage": stage}
    except (KeyError, TypeError, ET.ParseError):
        return {"error": "INVALID_REQUEST", "stage": stage}
    except Exception as exc:
        return {"error": "TASK_SCHEDULER_FAILED", "stage": stage, **com_codes(exc)}
    finally:
        # Release COM wrappers before the caller uninitializes the apartment.
        candidate = task = folder = service = None


def main():
    initialized = False
    pythoncom = None
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Invalid request")
        from .win32 import current_sid
        if request.get("sid") != current_sid():
            result = {"error": "TASK_IDENTITY_MISMATCH"}
        else:
            try:
                import pythoncom
                import win32security
                from win32com.client.dynamic import Dispatch
            except ImportError:
                result = {"error": "COM_UNAVAILABLE"}
            else:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                initialized = True
                result = execute_operation(request, lambda: Dispatch("Schedule.Service"),
                                           lambda identity: resolve_identity(identity, win32security))
    except (ValueError, TypeError):
        result = {"error": "INVALID_REQUEST"}
    except Exception as exc:
        result = {"error": "TASK_SCHEDULER_FAILED", "stage": "initialize_com", **com_codes(exc)}
    finally:
        if initialized:
            pythoncom.CoUninitialize()
    print(json.dumps(result, ensure_ascii=True))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
