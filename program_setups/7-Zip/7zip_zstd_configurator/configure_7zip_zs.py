from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import winreg


APP_REG_ROOT = r"Software\7-Zip-Zstandard"
CLASSES_ROOT = r"Software\Classes"
PROGID_PREFIX = "7-Zip-Zstandard."
GIB = 1024 ** 3

REQUESTED_EXTENSIONS = [
    "7z",
    "zip",
    "rar",
    "iso",
    "xz",
    "txz",
    "tar",
    "pcio",
    "cpio",
    "bz2",
    "bzip2",
    "tbz2",
    "tbz",
    "gz",
    "gzip",
    "tgz",
    "xar",
    "zst",
    "tzst",
    "zstd",
    "tzstd",
]

ICON_INDEX_BY_EXT = {
    "7z": 0,
    "zip": 1,
    "bz2": 2,
    "bzip2": 2,
    "tbz2": 2,
    "tbz": 2,
    "rar": 3,
    "iso": 8,
    "pcio": 12,
    "cpio": 12,
    "tar": 13,
    "gz": 14,
    "gzip": 14,
    "tgz": 14,
    "xar": 19,
    "xz": 23,
    "txz": 23,
    "zst": 25,
    "tzst": 25,
    "zstd": 31,
    "tzstd": 31,
}

REG_VIEW = getattr(winreg, "KEY_WOW64_64KEY", 0)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def refresh_shell_icons() -> None:
    shell32 = ctypes.windll.shell32
    shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    subprocess.run(
        ["ie4uinit.exe", "-show"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply 7-Zip Zstandard settings and all-user file associations."
    )
    parser.add_argument("--install-dir", type=Path, help="Installed 7-Zip Zstandard directory.")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing them.")
    parser.add_argument(
        "--no-elevate",
        action="store_true",
        help="Do not relaunch as Administrator before writing HKLM settings.",
    )
    parser.add_argument(
        "--no-large-page-privilege",
        action="store_true",
        help="Do not grant SeLockMemoryPrivilege to the current account.",
    )
    parser.add_argument(
        "--no-dark-mode",
        action="store_true",
        help="Do not set 7-Zip ZS dark mode.",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Do not notify Explorer that file associations changed.",
    )
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print("ERROR: this configurator only runs on Windows.", file=sys.stderr)
        return 2

    install_dir = args.install_dir or find_install_dir()
    if install_dir is None:
        print("ERROR: Could not auto-detect the install directory.", file=sys.stderr)
        print(r'Pass --install-dir "C:\Program Files\7-Zip-Zstandard".', file=sys.stderr)
        return 2
    install_dir = install_dir.resolve()

    if not looks_like_install_dir(install_dir):
        print(f"ERROR: {install_dir} does not look like a 7-Zip install directory.", file=sys.stderr)
        return 2

    if _should_elevate(args):
        return _relaunch_as_admin()

    total_ram = _get_total_physical_memory()
    mem_limit_gb = _compute_mem_limit_gb(total_ram)
    icon_provider = _icon_provider(install_dir)

    print(f"Install directory: {install_dir}")
    print(f"Detected RAM:      {total_ram / GIB:.2f} GiB")
    print(f"RAM limit:         {mem_limit_gb} GB")
    print(f"Icon provider:     {icon_provider}")
    print(f"Dry run:           {'yes' if args.dry_run else 'no'}")

    _set_user_settings(mem_limit_gb, args.dry_run)
    if not args.no_dark_mode:
        _set_dark_mode(install_dir, args.dry_run)

    if not args.no_large_page_privilege:
        _grant_large_page_privilege(args.dry_run)

    _set_all_user_associations(install_dir, icon_provider, args.dry_run)
    _warn_user_choice_overrides()

    if not args.dry_run and not args.no_refresh:
        refresh_shell_icons()
        print("Requested Explorer association/icon refresh.")

    print("Done.")
    return 0


def _should_elevate(args: argparse.Namespace) -> bool:
    return not args.dry_run and not args.no_elevate and not is_admin()


def _relaunch_as_admin() -> int:
    project_root = Path(__file__).resolve().parent
    params = subprocess.list2cmdline([str(project_root / "configure_7zip_zs.py"), *sys.argv[1:]])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(project_root),
        1,
    )
    if result <= 32:
        print(f"ERROR: elevation failed with ShellExecute result {result}.", file=sys.stderr)
        return 1
    return 0


def _set_user_settings(mem_limit_gb: int, dry_run: bool) -> None:
    _set_dword(winreg.HKEY_CURRENT_USER, APP_REG_ROOT, "LargePages", 1, dry_run)
    _set_dword(winreg.HKEY_CURRENT_USER, APP_REG_ROOT + r"\Extraction", "MemLimit", mem_limit_gb, dry_run)
    _set_dword(winreg.HKEY_CURRENT_USER, APP_REG_ROOT + r"\Options", "MenuIcons", 1, dry_run)


def _set_dark_mode(install_dir: Path, dry_run: bool) -> None:
    _set_dword(winreg.HKEY_CURRENT_USER, APP_REG_ROOT, "ColorMode", 1, dry_run)

    ini_path = install_dir / "7zDark.ini"
    if not ini_path.exists():
        print("No 7zDark.ini present; registry ColorMode controls dark mode.")
        return
    if dry_run:
        print(f"Would set {ini_path} [main] mode=1")
        return
    _update_ini_value(ini_path, "main", "mode", "1")
    print(f"Updated {ini_path} [main] mode=1.")


def _grant_large_page_privilege(dry_run: bool) -> None:
    if dry_run:
        print("Would grant SeLockMemoryPrivilege to the current account.")
        return
    try:
        _lsa_add_account_right("SeLockMemoryPrivilege")
    except OSError as exc:
        print(f"WARNING: could not grant SeLockMemoryPrivilege: {exc}", file=sys.stderr)
        print("         LargePages was still enabled in 7-Zip ZS settings.", file=sys.stderr)
    else:
        print("Granted SeLockMemoryPrivilege to the current account.")


def _set_all_user_associations(install_dir: Path, icon_provider: Path, dry_run: bool) -> None:
    command = f'"{install_dir / "7zFM.exe"}" "%1"'
    seen: set[str] = set()
    for ext in REQUESTED_EXTENSIONS:
        ext = ext.lower().lstrip(".")
        if ext in seen:
            continue
        seen.add(ext)

        icon_index = ICON_INDEX_BY_EXT.get(ext, 0)
        progid = PROGID_PREFIX + ext
        title = f"{ext} Archive"

        _set_string(winreg.HKEY_LOCAL_MACHINE, rf"{CLASSES_ROOT}\.{ext}", None, progid, dry_run)
        _set_string(winreg.HKEY_LOCAL_MACHINE, rf"{CLASSES_ROOT}\{progid}", None, title, dry_run)
        _set_string(
            winreg.HKEY_LOCAL_MACHINE,
            rf"{CLASSES_ROOT}\{progid}\DefaultIcon",
            None,
            f"{icon_provider},{icon_index}",
            dry_run,
        )
        _set_string(winreg.HKEY_LOCAL_MACHINE, rf"{CLASSES_ROOT}\{progid}\shell", None, "", dry_run)
        _set_string(winreg.HKEY_LOCAL_MACHINE, rf"{CLASSES_ROOT}\{progid}\shell\open", None, "", dry_run)
        _set_string(
            winreg.HKEY_LOCAL_MACHINE,
            rf"{CLASSES_ROOT}\{progid}\shell\open\command",
            None,
            command,
            dry_run,
        )

    print(f"{'Would set' if dry_run else 'Set'} {len(seen)} all-user association(s).")


def _warn_user_choice_overrides() -> None:
    overrides: list[str] = []
    for ext in REQUESTED_EXTENSIONS:
        subkey = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.{ext}\UserChoice"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ) as key:
                progid, _kind = winreg.QueryValueEx(key, "ProgId")
        except OSError:
            continue
        if not str(progid).lower().startswith(PROGID_PREFIX.lower()):
            overrides.append(f".{ext}={progid}")

    if overrides:
        joined = ", ".join(overrides)
        print(f"Note: current-user UserChoice overrides exist and can take precedence: {joined}")


def _update_ini_value(path: Path, section: str, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    section_header = f"[{section}]"
    in_section = False
    saw_section = False
    wrote_key = False
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section and not wrote_key:
                output.append(f"{key}={value}\n")
                wrote_key = True
            in_section = stripped.lower() == section_header.lower()
            saw_section = saw_section or in_section

        if in_section and _ini_key_name(stripped).lower() == key.lower():
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            output.append(f"{key}={value}{newline}")
            wrote_key = True
        else:
            output.append(line)

    if saw_section and in_section and not wrote_key:
        output.append(f"{key}={value}\n")
    elif not saw_section:
        if output and not output[-1].endswith(("\n", "\r")):
            output.append("\n")
        output.append(f"\n{section_header}\n{key}={value}\n")

    path.write_text("".join(output), encoding="utf-8")


def _ini_key_name(stripped_line: str) -> str:
    if not stripped_line or stripped_line.startswith(("#", ";")):
        return ""
    if "=" not in stripped_line:
        return ""
    return stripped_line.split("=", 1)[0].strip()


def _icon_provider(install_dir: Path) -> Path:
    icon_dll = install_dir / "7z.dll"
    if icon_dll.exists():
        return icon_dll
    return install_dir / "7zFM.exe"


def _set_dword(root, subkey: str, name: str, value: int, dry_run: bool) -> None:
    if dry_run:
        print(f"Would set {_root_label(root)}\\{subkey}\\{name} = DWORD {value}")
        return
    with winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_WRITE | REG_VIEW) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))


def _set_string(root, subkey: str, name: str | None, value: str, dry_run: bool) -> None:
    display_name = "(Default)" if name is None else name
    if dry_run:
        print(f"Would set {_root_label(root)}\\{subkey}\\{display_name} = {value}")
        return
    with winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_WRITE | REG_VIEW) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _root_label(root) -> str:
    if root == winreg.HKEY_CURRENT_USER:
        return "HKCU"
    if root == winreg.HKEY_LOCAL_MACHINE:
        return "HKLM"
    return str(root)


def _get_total_physical_memory() -> int:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return int(status.ullTotalPhys)


def _compute_mem_limit_gb(total_ram_bytes: int) -> int:
    limit_bytes = (total_ram_bytes * 25 + 99) // 100
    limit_gb = max(1, (limit_bytes + GIB - 1) // GIB)

    ram_size_gb = max(1, (total_ram_bytes + (1 << 29)) >> 30)
    max_ui_gb = 1 if ram_size_gb <= 1 else min(1 << 14, ram_size_gb - 1)
    return min(int(limit_gb), int(max_ui_gb))


def _lsa_add_account_right(right_name: str) -> None:
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    class LSA_UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class LSA_OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.c_void_p),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    class TOKEN_USER(ctypes.Structure):
        _fields_ = [("User", SID_AND_ATTRIBUTES)]

    TOKEN_QUERY = 0x0008
    TOKEN_USER_CLASS = 1
    POLICY_CREATE_ACCOUNT = 0x0010
    POLICY_LOOKUP_NAMES = 0x0800

    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.LsaOpenPolicy.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(LSA_OBJECT_ATTRIBUTES),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.LsaOpenPolicy.restype = wintypes.LONG
    advapi32.LsaAddAccountRights.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(LSA_UNICODE_STRING),
        wintypes.DWORD,
    ]
    advapi32.LsaAddAccountRights.restype = wintypes.LONG
    advapi32.LsaClose.argtypes = [wintypes.HANDLE]
    advapi32.LsaClose.restype = wintypes.LONG
    advapi32.LsaNtStatusToWinError.argtypes = [wintypes.LONG]
    advapi32.LsaNtStatusToWinError.restype = wintypes.ULONG

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise ctypes.WinError()

    policy = wintypes.HANDLE()
    try:
        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
        token_buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token,
            TOKEN_USER_CLASS,
            token_buffer,
            needed.value,
            ctypes.byref(needed),
        ):
            raise ctypes.WinError()

        token_user = ctypes.cast(token_buffer, ctypes.POINTER(TOKEN_USER)).contents

        attrs = LSA_OBJECT_ATTRIBUTES()
        attrs.Length = ctypes.sizeof(attrs)
        access = POLICY_CREATE_ACCOUNT | POLICY_LOOKUP_NAMES
        status = advapi32.LsaOpenPolicy(None, ctypes.byref(attrs), access, ctypes.byref(policy))
        if status != 0:
            _raise_lsa_error(status)

        right_buffer = ctypes.create_unicode_buffer(right_name)
        right = LSA_UNICODE_STRING()
        right.Length = len(right_name) * ctypes.sizeof(wintypes.WCHAR)
        right.MaximumLength = (len(right_name) + 1) * ctypes.sizeof(wintypes.WCHAR)
        right.Buffer = ctypes.cast(right_buffer, wintypes.LPWSTR)

        status = advapi32.LsaAddAccountRights(policy, token_user.User.Sid, ctypes.byref(right), 1)
        if status != 0:
            _raise_lsa_error(status)
    finally:
        if policy:
            advapi32.LsaClose(policy)
        if token:
            kernel32.CloseHandle(token)


def _raise_lsa_error(status: int) -> None:
    error = ctypes.windll.advapi32.LsaNtStatusToWinError(status)
    raise OSError(error, ctypes.FormatError(error))


if __name__ == "__main__":
    raise SystemExit(main())
