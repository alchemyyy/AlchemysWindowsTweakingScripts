from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import subprocess
import time


ERROR_MORE_DATA = 234
ERROR_SUCCESS = 0

CCH_RM_SESSION_KEY = 32
CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63

RM_FORCE_SHUTDOWN = 0x1

SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", FILETIME),
    ]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
        ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.ULONG),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


@dataclass(frozen=True)
class LockingProcess:
    pid: int
    app_name: str
    service_name: str
    restartable: bool

    @property
    def is_explorer(self) -> bool:
        name = self.app_name.lower()
        return name in {"explorer", "explorer.exe", "windows explorer"}


rstrtmgr = ctypes.WinDLL("rstrtmgr", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

rstrtmgr.RmStartSession.argtypes = (
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
    wintypes.LPWSTR,
)
rstrtmgr.RmStartSession.restype = wintypes.DWORD
rstrtmgr.RmRegisterResources.argtypes = (
    wintypes.DWORD,
    wintypes.UINT,
    ctypes.POINTER(wintypes.LPCWSTR),
    wintypes.UINT,
    ctypes.POINTER(RM_UNIQUE_PROCESS),
    wintypes.UINT,
    ctypes.POINTER(wintypes.LPCWSTR),
)
rstrtmgr.RmRegisterResources.restype = wintypes.DWORD
rstrtmgr.RmGetList.argtypes = (
    wintypes.DWORD,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(RM_PROCESS_INFO),
    ctypes.POINTER(wintypes.DWORD),
)
rstrtmgr.RmGetList.restype = wintypes.DWORD
rstrtmgr.RmShutdown.argtypes = (wintypes.DWORD, wintypes.ULONG, ctypes.c_void_p)
rstrtmgr.RmShutdown.restype = wintypes.DWORD
rstrtmgr.RmEndSession.argtypes = (wintypes.DWORD,)
rstrtmgr.RmEndSession.restype = wintypes.DWORD

kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL


def close_locking_processes(
    paths: list[Path],
    *,
    force: bool = True,
    restart_explorer: bool = True,
    wait_seconds: float = 2.0,
) -> list[LockingProcess]:
    paths = [path.resolve() for path in paths if path.exists()]
    if not paths:
        return []

    session, key = _start_session()
    try:
        _register_files(session, paths)
        processes = _get_locking_processes(session)
        processes = [process for process in processes if process.pid != os.getpid()]
        if not processes:
            return []

        had_explorer = any(process.is_explorer for process in processes)
        flags = RM_FORCE_SHUTDOWN if force else 0
        result = rstrtmgr.RmShutdown(session, flags, None)

        time.sleep(wait_seconds)
        remaining = [process for process in processes if _process_exists(process.pid)]
        if result != ERROR_SUCCESS or remaining:
            _taskkill(remaining or processes)
            time.sleep(0.5)

        if had_explorer and restart_explorer and not _explorer_is_running():
            subprocess.Popen(["explorer.exe"], close_fds=True)

        return processes
    finally:
        rstrtmgr.RmEndSession(session)


def get_locking_processes(paths: list[Path]) -> list[LockingProcess]:
    paths = [path.resolve() for path in paths if path.exists()]
    if not paths:
        return []

    session, key = _start_session()
    try:
        _register_files(session, paths)
        return _get_locking_processes(session)
    finally:
        rstrtmgr.RmEndSession(session)


def _start_session() -> tuple[int, ctypes.Array]:
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)
    result = rstrtmgr.RmStartSession(ctypes.byref(session), 0, key)
    if result != ERROR_SUCCESS:
        raise OSError(result, "RmStartSession failed")
    return int(session.value), key


def _register_files(session: int, paths: list[Path]) -> None:
    strings = [str(path) for path in paths]
    array = (wintypes.LPCWSTR * len(strings))(*strings)
    result = rstrtmgr.RmRegisterResources(session, len(strings), array, 0, None, 0, None)
    if result != ERROR_SUCCESS:
        raise OSError(result, "RmRegisterResources failed")


def _get_locking_processes(session: int) -> list[LockingProcess]:
    needed = wintypes.UINT(0)
    count = wintypes.UINT(0)
    reboot_reasons = wintypes.DWORD(0)
    result = rstrtmgr.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None, ctypes.byref(reboot_reasons))
    if result == ERROR_SUCCESS:
        return []
    if result != ERROR_MORE_DATA:
        raise OSError(result, "RmGetList failed")

    count = wintypes.UINT(needed.value)
    process_info = (RM_PROCESS_INFO * count.value)()
    result = rstrtmgr.RmGetList(
        session,
        ctypes.byref(needed),
        ctypes.byref(count),
        process_info,
        ctypes.byref(reboot_reasons),
    )
    if result != ERROR_SUCCESS:
        raise OSError(result, "RmGetList failed")

    processes: list[LockingProcess] = []
    seen: set[int] = set()
    for i in range(count.value):
        item = process_info[i]
        pid = int(item.Process.dwProcessId)
        if pid in seen or pid in (0, 4):
            continue
        seen.add(pid)
        processes.append(
            LockingProcess(
                pid=pid,
                app_name=str(item.strAppName).rstrip("\x00"),
                service_name=str(item.strServiceShortName).rstrip("\x00"),
                restartable=bool(item.bRestartable),
            )
        )
    return processes


def _process_exists(pid: int) -> bool:
    handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def _taskkill(processes: list[LockingProcess]) -> None:
    for process in processes:
        if process.pid in (0, 4, os.getpid()):
            continue
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _explorer_is_running() -> bool:
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq explorer.exe", "/NH"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return "explorer.exe" in result.stdout.lower()
