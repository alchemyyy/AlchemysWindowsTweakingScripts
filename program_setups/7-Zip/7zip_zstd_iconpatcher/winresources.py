from __future__ import annotations

from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
from pathlib import Path


ResourceName = int | str

RT_ICON = 3
RT_GROUP_ICON = 14

LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ENUMRESNAMEPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.LPARAM,
)

ENUMRESLANGPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMODULE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.WORD,
    wintypes.LPARAM,
)

kernel32.LoadLibraryExW.argtypes = (wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD)
kernel32.LoadLibraryExW.restype = wintypes.HMODULE
kernel32.FreeLibrary.argtypes = (wintypes.HMODULE,)
kernel32.FreeLibrary.restype = wintypes.BOOL
kernel32.EnumResourceNamesW.argtypes = (
    wintypes.HMODULE,
    wintypes.LPCWSTR,
    ENUMRESNAMEPROC,
    wintypes.LPARAM,
)
kernel32.EnumResourceNamesW.restype = wintypes.BOOL
kernel32.EnumResourceLanguagesW.argtypes = (
    wintypes.HMODULE,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ENUMRESLANGPROC,
    wintypes.LPARAM,
)
kernel32.EnumResourceLanguagesW.restype = wintypes.BOOL
kernel32.FindResourceExW.argtypes = (
    wintypes.HMODULE,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.WORD,
)
kernel32.FindResourceExW.restype = wintypes.HRSRC
kernel32.LoadResource.argtypes = (wintypes.HMODULE, wintypes.HRSRC)
kernel32.LoadResource.restype = wintypes.HGLOBAL
kernel32.LockResource.argtypes = (wintypes.HGLOBAL,)
kernel32.LockResource.restype = ctypes.c_void_p
kernel32.SizeofResource.argtypes = (wintypes.HMODULE, wintypes.HRSRC)
kernel32.SizeofResource.restype = wintypes.DWORD
kernel32.BeginUpdateResourceW.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
kernel32.UpdateResourceW.argtypes = (
    wintypes.HANDLE,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.WORD,
    wintypes.LPVOID,
    wintypes.DWORD,
)
kernel32.UpdateResourceW.restype = wintypes.BOOL
kernel32.EndUpdateResourceW.argtypes = (wintypes.HANDLE, wintypes.BOOL)
kernel32.EndUpdateResourceW.restype = wintypes.BOOL


def _raise_last_error(prefix: str) -> None:
    err = ctypes.get_last_error()
    if err:
        raise OSError(err, f"{prefix}: {ctypes.FormatError(err).strip()}")
    raise OSError(f"{prefix}: Windows API call failed")


def _make_resource(value: ResourceName) -> wintypes.LPCWSTR:
    if isinstance(value, int):
        return ctypes.cast(ctypes.c_void_p(value), wintypes.LPCWSTR)
    return wintypes.LPCWSTR(value)


def _resource_from_ptr(ptr: int | None) -> ResourceName:
    value = 0 if ptr is None else int(ptr)
    if value <= 0xFFFF:
        return value
    return ctypes.wstring_at(value)


class ResourceModule(AbstractContextManager["ResourceModule"]):
    def __init__(self, path: Path):
        self.path = path
        self.handle: wintypes.HMODULE | None = None
        self._callbacks: list[object] = []

    def __enter__(self) -> "ResourceModule":
        flags = LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
        handle = kernel32.LoadLibraryExW(str(self.path), None, flags)
        if not handle:
            _raise_last_error(f"LoadLibraryExW({self.path})")
        self.handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle:
            kernel32.FreeLibrary(self.handle)
            self.handle = None
        self._callbacks.clear()

    def enum_names(self, resource_type: int) -> list[ResourceName]:
        if not self.handle:
            raise RuntimeError("resource module is not open")

        names: list[ResourceName] = []

        @ENUMRESNAMEPROC
        def callback(_module, _rtype, name, _param):
            names.append(_resource_from_ptr(name))
            return True

        self._callbacks.append(callback)
        ok = kernel32.EnumResourceNamesW(
            self.handle,
            _make_resource(resource_type),
            callback,
            0,
        )
        if not ok:
            err = ctypes.get_last_error()
            if err in (1812, 1813):  # no resource section / type not found
                return []
            _raise_last_error(f"EnumResourceNamesW({self.path})")
        return names

    def enum_languages(self, resource_type: int, name: ResourceName) -> list[int]:
        if not self.handle:
            raise RuntimeError("resource module is not open")

        languages: list[int] = []

        @ENUMRESLANGPROC
        def callback(_module, _rtype, _name, lang, _param):
            languages.append(int(lang))
            return True

        self._callbacks.append(callback)
        ok = kernel32.EnumResourceLanguagesW(
            self.handle,
            _make_resource(resource_type),
            _make_resource(name),
            callback,
            0,
        )
        if not ok:
            err = ctypes.get_last_error()
            if err in (1814, 1815):  # name/language not found
                return []
            _raise_last_error(f"EnumResourceLanguagesW({self.path}, {name!r})")
        return languages

    def read(self, resource_type: int, name: ResourceName, language: int) -> bytes:
        if not self.handle:
            raise RuntimeError("resource module is not open")

        resource = kernel32.FindResourceExW(
            self.handle,
            _make_resource(resource_type),
            _make_resource(name),
            language,
        )
        if not resource:
            _raise_last_error(f"FindResourceExW({self.path}, {resource_type}, {name!r})")
        size = kernel32.SizeofResource(self.handle, resource)
        if size == 0:
            _raise_last_error(f"SizeofResource({self.path}, {resource_type}, {name!r})")
        loaded = kernel32.LoadResource(self.handle, resource)
        if not loaded:
            _raise_last_error(f"LoadResource({self.path}, {resource_type}, {name!r})")
        locked = kernel32.LockResource(loaded)
        if not locked:
            _raise_last_error(f"LockResource({self.path}, {resource_type}, {name!r})")
        return ctypes.string_at(locked, size)


class ResourceUpdater(AbstractContextManager["ResourceUpdater"]):
    def __init__(self, path: Path):
        self.path = path
        self.handle: wintypes.HANDLE | None = None
        self._discard = True

    def __enter__(self) -> "ResourceUpdater":
        handle = kernel32.BeginUpdateResourceW(str(self.path), False)
        if not handle:
            _raise_last_error(f"BeginUpdateResourceW({self.path})")
        self.handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle:
            discard = bool(exc_type or self._discard)
            ok = kernel32.EndUpdateResourceW(self.handle, discard)
            self.handle = None
            if not ok and not discard:
                _raise_last_error(f"EndUpdateResourceW({self.path})")

    def update(self, resource_type: int, name: ResourceName, language: int, data: bytes) -> None:
        if not self.handle:
            raise RuntimeError("resource updater is not open")

        buffer = ctypes.create_string_buffer(data)
        ok = kernel32.UpdateResourceW(
            self.handle,
            _make_resource(resource_type),
            _make_resource(name),
            language,
            buffer,
            len(data),
        )
        if not ok:
            _raise_last_error(f"UpdateResourceW({self.path}, {resource_type}, {name!r})")

    def commit(self) -> None:
        self._discard = False
