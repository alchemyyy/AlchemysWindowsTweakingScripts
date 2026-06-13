from __future__ import annotations

from pathlib import Path
import os
import winreg


def _candidate_from_registry(root, subkey: str, value_name: str | None, access: int) -> Path | None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | access) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None

    path = Path(str(value).strip('"'))
    if path.name.lower() == "7zfm.exe":
        path = path.parent
    return path if path.exists() else None


def find_install_dir() -> Path | None:
    views = [0]
    for flag in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        if hasattr(winreg, flag):
            views.append(getattr(winreg, flag))

    roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    app_roots = [r"Software\7-Zip-Zstandard", r"Software\7-Zip"]
    value_names = ["Path64", "Path32", "Path"]
    for access in views:
        for root in roots:
            for app_root in app_roots:
                for value_name in value_names:
                    path = _candidate_from_registry(root, app_root, value_name, access)
                    if path and looks_like_install_dir(path):
                        return path

    app_paths = r"Software\Microsoft\Windows\CurrentVersion\App Paths\7zFM.exe"
    for access in views:
        path = _candidate_from_registry(winreg.HKEY_LOCAL_MACHINE, app_paths, None, access)
        if path and looks_like_install_dir(path):
            return path

    defaults = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip-Zstandard",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "7-Zip-Zstandard",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "7-Zip",
    ]
    for path in defaults:
        if looks_like_install_dir(path):
            return path
    return None


def looks_like_install_dir(path: Path) -> bool:
    return path.is_dir() and any((path / name).exists() for name in ("7zFM.exe", "7z.dll"))
