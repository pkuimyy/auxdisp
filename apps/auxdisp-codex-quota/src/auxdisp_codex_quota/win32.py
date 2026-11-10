"""Small typed Win32 boundary for user identity, mutexes, and stop events."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import os

from .paths import APP_ID


class ServiceError(RuntimeError):
    """An actionable lifecycle error with no subprocess output or credentials."""


class InstanceBusy(ServiceError):
    pass


def kernel():
    if os.name != "nt":
        raise ServiceError("Background task management is supported only on Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateMutexW": ([w.LPVOID, w.BOOL, w.LPCWSTR], w.HANDLE),
        "OpenMutexW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "ReleaseMutex": ([w.HANDLE], w.BOOL),
        "CreateEventW": ([w.LPVOID, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
        "OpenEventW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        "SetEvent": ([w.HANDLE], w.BOOL),
        "ResetEvent": ([w.HANDLE], w.BOOL),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "CloseHandle": ([w.HANDLE], w.BOOL),
        "GetCurrentProcess": ([], w.HANDLE),
        "LocalFree": ([w.HLOCAL], w.HLOCAL),
        "GetSystemDirectoryW": ([w.LPWSTR, w.UINT], w.UINT),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    return api


def checked(value):
    if not value:
        raise ServiceError(f"Windows synchronization failed (error {ctypes.get_last_error()})")
    return value


def current_sid():
    api = kernel()
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    security.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    security.OpenProcessToken.restype = w.BOOL
    security.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)]
    security.GetTokenInformation.restype = w.BOOL
    security.ConvertSidToStringSidW.argtypes = [w.LPVOID, ctypes.POINTER(w.LPWSTR)]
    security.ConvertSidToStringSidW.restype = w.BOOL
    token = w.HANDLE()
    checked(security.OpenProcessToken(api.GetCurrentProcess(), 8, ctypes.byref(token)))
    try:
        size = w.DWORD()
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            checked(False)
        data = ctypes.create_string_buffer(size.value)
        checked(security.GetTokenInformation(token, 1, data, size, ctypes.byref(size)))
        sid = ctypes.cast(data, ctypes.POINTER(w.LPVOID))[0]
        value = w.LPWSTR()
        checked(security.ConvertSidToStringSidW(sid, ctypes.byref(value)))
        try:
            return value.value
        finally:
            api.LocalFree(ctypes.cast(value, w.HLOCAL))
    finally:
        api.CloseHandle(token)


def system_directory():
    data = ctypes.create_unicode_buffer(32768)
    checked(kernel().GetSystemDirectoryW(data, len(data)))
    return data.value


class StopEvent:
    def __init__(self, api, handle):
        self.api, self.handle = api, handle

    def wait(self, seconds=0):
        result = self.api.WaitForSingleObject(self.handle, max(0, min(int(seconds * 1000), 0xFFFFFFFE)))
        if result == 0xFFFFFFFF:
            checked(False)
        return result == 0

    def is_set(self):
        return self.wait(0)


class WindowsIPC:
    def __init__(self, sid=None):
        self.sid = sid or current_sid()
        self.api = kernel()
        # SID-qualified Global objects also exclude duplicates in another logon session.
        self.prefix = f"Global\\{APP_ID}-{self.sid}"

    @contextmanager
    def lock(self, suffix="instance", timeout=0):
        handle = checked(self.api.CreateMutexW(None, False, self.prefix + "-" + suffix))
        acquired = False
        try:
            result = self.api.WaitForSingleObject(handle, int(timeout * 1000))
            if result == 258:
                raise InstanceBusy("auxdisp-codex-quota is already running or being managed")
            if result not in (0, 128):  # abandoned mutexes can be acquired after a crash
                checked(False)
            acquired = True
            yield
        finally:
            if acquired:
                self.api.ReleaseMutex(handle)
            self.api.CloseHandle(handle)

    def running(self):
        handle = self.api.OpenMutexW(0x100001, False, self.prefix + "-instance")
        if not handle:
            if ctypes.get_last_error() == 2:
                return False
            checked(False)
        try:
            result = self.api.WaitForSingleObject(handle, 0)
            if result in (0, 128):
                self.api.ReleaseMutex(handle)
                return False
            if result != 258:
                checked(False)
            return True
        finally:
            self.api.CloseHandle(handle)

    @contextmanager
    def stop_event(self):
        handle = checked(self.api.CreateEventW(None, True, False, self.prefix + "-stop"))
        try:
            checked(self.api.ResetEvent(handle))
            yield StopEvent(self.api, handle)
        finally:
            self.api.CloseHandle(handle)

    def signal_stop(self):
        handle = self.api.OpenEventW(2, False, self.prefix + "-stop")
        if not handle:
            if ctypes.get_last_error() == 2:
                return False
            checked(False)
        try:
            checked(self.api.SetEvent(handle))
            return True
        finally:
            self.api.CloseHandle(handle)
