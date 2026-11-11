"""Read-only Direct COM feasibility probe; never used as a runtime fallback.

Requires pywin32 only in the experiment environment. Queries exactly this user's
AuxDisp task; never enumerates tasks or registers/modifies/deletes anything.
"""

import argparse
import json
from pathlib import Path


MISSING = {0x80070002, 0x8004130F}
PREFIXES = ("-I -m auxdisp_codex_quota._background ", "-E -P -m auxdisp_codex_quota._background ")
MARKER = "auxdisp-codex-quota managed background task v1 "


def resolve_identity(identity, security):
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("Empty identity")
    if identity.upper().startswith("S-"):
        value = security.ConvertStringSidToSid(identity)
    else:
        value = security.LookupAccountName(None, identity)[0]
    return security.ConvertSidToStringSid(value)


def error_metadata(exc):
    codes = {}
    value = getattr(exc, "hresult", None)
    if type(value) is int:
        codes["hresult"] = value & 0xFFFFFFFF
    info = getattr(exc, "excepinfo", None)
    if isinstance(info, tuple) and len(info) > 5 and type(info[5]) is int:
        codes["scode"] = info[5] & 0xFFFFFFFF
    return codes


def probe(create_service, sid, resolve_sid):
    result = {"status": "FAILED", "stage": "create_com", "completed": []}

    def step(stage, action):
        result["stage"] = stage
        value = action()
        result["completed"].append(stage)
        return value

    try:
        service = step("create_com", create_service)
        step("connect", service.Connect)
        folder = step("get_root", lambda: service.GetFolder("\\"))
        name = "auxdisp-codex-quota-" + sid
        try:
            task = step("get_task", lambda: folder.GetTask(name))
        except Exception as exc:
            if MISSING.intersection(error_metadata(exc).values()):
                result.update(status="OK", registered=False)
                return result
            raise
        definition = step("read_definition", lambda: task.Definition)
        identity = step("read_identity", lambda: definition.Principal.UserId)
        try:
            normalized = step("resolve_identity", lambda: resolve_sid(identity))
        except Exception:
            result.update(status="REFUSED", error="TASK_IDENTITY_UNRESOLVED")
            return result
        if normalized != sid:
            result.update(status="REFUSED", error="TASK_IDENTITY_MISMATCH")
            return result
        description = step("read_marker", lambda: definition.RegistrationInfo.Description)
        if not isinstance(description, str) or not description.startswith(MARKER):
            result.update(status="REFUSED", error="TASK_MARKER_MISMATCH")
            return result
        actions = step("read_actions", lambda: definition.Actions)
        if actions.Count != 1:
            result.update(status="REFUSED", error="TASK_ACTION_MISMATCH")
            return result
        arguments = step("read_arguments", lambda: actions.Item(1).Arguments)
        if not isinstance(arguments, str) or not arguments.startswith(PREFIXES):
            result.update(status="REFUSED", error="TASK_ACTION_MISMATCH")
            return result
        result.update(status="OK", registered=True, identity_matches=True, marker_matches=True,
                      identity_form="sid" if identity.upper().startswith("S-") else "name",
                      action_count=1, launch_format="legacy" if arguments.startswith("-I ") else "user_site",
                      task_name_matches=step("read_name", lambda: task.Name).casefold() == name.casefold())
    except Exception as exc:
        codes = error_metadata(exc)
        result.update(codes, error="ACCESS_DENIED" if 0x80070005 in codes.values() else "COM_PROBE_FAILED",
                      exception_type=type(exc).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional safe metadata JSON record")
    args = parser.parse_args()
    initialized = False
    result = {"status": "FAILED", "stage": "import_dependency"}
    try:
        import pythoncom
        import win32security
        from win32com.client import Dispatch
        from auxdisp_codex_quota.win32 import current_sid

        result["stage"] = "initialize_com"
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        initialized = True

        result = probe(lambda: Dispatch("Schedule.Service"), current_sid(),
                       lambda identity: resolve_identity(identity, win32security))
    except Exception as exc:
        codes = error_metadata(exc)
        result.update(codes, error="ACCESS_DENIED" if 0x80070005 in codes.values() else "COM_PROBE_FAILED",
                      exception_type=type(exc).__name__)
    finally:
        if initialized:
            pythoncom.CoUninitialize()
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
