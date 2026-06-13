#!/usr/bin/env python3
"""
WindhawkBAR - simple JSON/assets backup and restore for Windhawk.

The backup format is intentionally plain:
  backup.json  - processed registry/INI/userprofile/mod state
  assets/      - source files and compiled DLLs that cannot be represented as JSON

During restore, normal catalog mods are downloaded from the Windhawk mod
repository by default. Archived assets are used for local mods, offline mode,
or automatic fallback if online downloads fail. Use --json-only to restore
from backup.json without requiring the assets directory.
"""

from __future__ import annotations

import argparse
import configparser
from contextlib import contextmanager
import ctypes
import datetime as _dt
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - Windhawk is Windows-only.
    winreg = None  # type: ignore[assignment]


APP_NAME = "WindhawkBAR"
FORMAT_VERSION = 1

DEFAULT_WINDHAWK_ROOT = Path(os.path.expandvars(r"%ProgramData%\Windhawk"))
BACKUP_ZIP_NAME = "WindhawkBARResult.zip"
WINDHAWK_SERVICE_NAME = "Windhawk"
REG_BASE = r"SOFTWARE\Windhawk"
MODS_URL_ROOT = "https://mods.windhawk.net/mods/"
WINDHAWK_RELEASES_API = "https://api.github.com/repos/ramensoftware/windhawk/releases/latest"
WINDHAWK_RELEASES_PAGE = "https://github.com/ramensoftware/windhawk/releases"
WINDHAWK_INSTALLER_ASSET = "windhawk_setup.exe"
USER_AGENT = "WindhawkBAR/1.0"

CONFIG_FIELD_TYPES = {
    "LibraryFileName": "string",
    "Disabled": "dword",
    "LoggingEnabled": "dword",
    "DebugLoggingEnabled": "dword",
    "Include": "string",
    "Exclude": "string",
    "IncludeCustom": "string",
    "ExcludeCustom": "string",
    "IncludeExcludeCustomOnly": "dword",
    "PatternsMatchCriticalSystemProcesses": "dword",
    "Architecture": "string",
    "Version": "string",
    "SettingsChangeTime": "dword",
}

REPOSITORY_CONFIG_FIELDS = {
    "LibraryFileName",
    "Disabled",
    "Include",
    "Exclude",
    "Architecture",
    "Version",
}

REG_TYPE_NAMES = {
    1: "REG_SZ",
    2: "REG_EXPAND_SZ",
    3: "REG_BINARY",
    4: "REG_DWORD",
    7: "REG_MULTI_SZ",
    11: "REG_QWORD",
}

REG_TYPES_BY_NAME = {v: k for k, v in REG_TYPE_NAMES.items()}


class WindhawkBarError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser().resolve()


def resolve_backup_zip_path(value: str | Path) -> Path:
    path = Path(os.path.expandvars(str(value))).expanduser()
    if path.suffix.lower() == ".zip":
        return path.resolve()
    return (path / BACKUP_ZIP_NAME).resolve()


def rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def validate_windhawk_root(root: Path) -> None:
    sentinels = windhawk_root_sentinels(root)
    if not windhawk_root_detected(root):
        expected = ", ".join(str(p) for p in sentinels)
        raise WindhawkBarError(
            f"Not a recognizable Windhawk data path: {root}\n"
            f"Expected at least one of: {expected}"
        )


def windhawk_root_sentinels(root: Path) -> list[Path]:
    return [
        root / "ModsSource",
        root / "Engine" / "Mods",
        root / "userprofile.json",
    ]


def windhawk_root_detected(root: Path) -> bool:
    return root.exists() and any(p.exists() for p in windhawk_root_sentinels(root))


def safe_asset_stem(mod_id: str) -> str:
    readable = re.sub(r"[^0-9A-Za-z._@-]+", "_", mod_id).strip("._") or "mod"
    digest = hashlib.sha1(mod_id.encode("utf-8")).hexdigest()[:8]
    return f"{readable}_{digest}"


def checked_mod_id(mod_id: str) -> str:
    if "\\" in mod_id or "/" in mod_id or mod_id in {"", ".", ".."}:
        raise WindhawkBarError(f"Unsafe mod id in backup: {mod_id!r}")
    return mod_id


def request_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def request_text(url: str) -> str:
    return request_bytes(url).decode("utf-8-sig")


def request_json(url: str) -> Any:
    return json.loads(request_text(url))


def download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as response:
        with target.open("wb") as fh:
            shutil.copyfileobj(response, fh)


def quote_url_part(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def mod_latest_source_url(mod_id: str) -> str:
    return f"{MODS_URL_ROOT}{quote_url_part(mod_id)}.wh.cpp"


def mod_version_source_url(mod_id: str, version: str) -> str:
    return (
        f"{MODS_URL_ROOT}{quote_url_part(mod_id)}/"
        f"{quote_url_part(version)}.wh.cpp"
    )


def mod_dll_url(mod_id: str, version: str, arch_subfolder: str) -> str:
    return (
        f"{MODS_URL_ROOT}{quote_url_part(mod_id)}/"
        f"{quote_url_part(version)}_{arch_subfolder}.dll"
    )


def normalize_source_newlines(source: str) -> str:
    return re.sub(r"\r\n|\r|\n", "\r\n", source)


def extract_mod_metadata(source: str) -> dict[str, Any]:
    match = re.search(
        r"^//[ \t]+==WindhawkMod==[ \t]*$([\s\S]+?)"
        r"^//[ \t]+==/WindhawkMod==[ \t]*$",
        source,
        flags=re.MULTILINE,
    )
    if not match:
        return {}

    metadata_raw: dict[str, list[str]] = {}
    for line in match.group(1).splitlines():
        line = line.rstrip()
        if not line.strip():
            continue

        line_match = re.match(
            r"^//[ \t]+@(_?[A-Za-z]+)(?::[a-z]{2}(?:-[A-Z]{2})?)?[ \t]+(.*)$",
            line,
        )
        if not line_match:
            continue

        key = line_match.group(1)
        if key.startswith("_"):
            continue
        metadata_raw.setdefault(key, []).append(line_match.group(2))

    metadata: dict[str, Any] = {}
    for key, values in metadata_raw.items():
        if key in {"include", "exclude", "architecture"}:
            metadata[key] = values
        elif values:
            metadata[key] = values[0]

    return metadata


def metadata_pipe_list(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return ""


def parse_pipe_list(value: Any) -> list[str]:
    if not value:
        return []
    return str(value).split("|")


def architecture_subfolders(architectures: list[str], arm64_enabled: bool) -> list[str]:
    result: list[str] = []
    archs = architectures or ["x86", "x86-64"]

    def add(subfolder: str) -> None:
        if subfolder not in result:
            result.append(subfolder)

    for arch in archs:
        if arch == "x86":
            add("32")
        elif arch == "x86-64":
            add("64")
            if arm64_enabled:
                add("arm64")
        elif arch == "amd64":
            add("64")
        elif arch == "arm64":
            if arm64_enabled:
                add("arm64")
        else:
            raise WindhawkBarError(f"Unsupported architecture in metadata: {arch}")

    return result


def host_arm64_enabled() -> bool:
    return platform.machine().lower() in {"arm64", "aarch64"}


def random_dll_name(mod_id: str, version: str) -> str:
    return f"{mod_id}_{version}_{random.randint(100000, 999999)}.dll"


def delete_old_mod_dlls(root: Path, mod_id: str, current_dll_name: str, subfolders: list[str], dry_run: bool) -> None:
    for subfolder in subfolders:
        folder = root / "Engine" / "Mods" / subfolder
        if not folder.is_dir():
            continue

        for item in folder.iterdir():
            if not item.is_file() or item.name == current_dll_name:
                continue
            if not item.name.startswith(mod_id + "_") or not item.name.endswith(".dll"):
                continue

            filename_part = item.name[len(mod_id) + 1 : -4]
            if not re.search(r"(^|_)[0-9]+$", filename_part):
                continue

            if dry_run:
                print(f"Would delete old DLL: {item}")
            else:
                try:
                    item.unlink()
                except OSError:
                    pass


def run_sc(action: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["sc", action, WINDHAWK_SERVICE_NAME],
            text=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = (completed.stdout + completed.stderr).strip()
        return completed.returncode == 0, output
    except OSError as exc:
        return False, str(exc)


def stop_service() -> None:
    ok, out = run_sc("stop")
    if ok:
        print("Stopped Windhawk service.")
        return
    if "1062" in out or "not started" in out.lower():
        print("Windhawk service was not running.")
        return
    print(f"Warning: failed to stop Windhawk service: {out}")


def start_service() -> None:
    ok, out = run_sc("start")
    if ok:
        print("Started Windhawk service.")
        return
    if "1056" in out or "already running" in out.lower():
        print("Windhawk service was already running.")
        return
    print(f"Warning: failed to start Windhawk service: {out}")


def detect_portable(root: Path, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit

    if winreg is None:
        return True

    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            REG_BASE + r"\Engine\Mods",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        winreg.CloseKey(key)
        return False
    except OSError:
        pass

    return any((root / "Engine" / "Mods").glob("*.ini"))


def windhawk_root_candidates(root: Path, portable_install: bool) -> list[Path]:
    candidates = [root]
    if portable_install:
        appdata_root = root / "AppData"
        if appdata_root not in candidates:
            candidates.append(appdata_root)
    return candidates


def find_detected_windhawk_root(root: Path, portable_install: bool) -> Path | None:
    for candidate in windhawk_root_candidates(root, portable_install):
        if windhawk_root_detected(candidate):
            return candidate
    return None


def windhawk_portable_install_dir(root: Path) -> Path:
    if root.name.lower() == "appdata":
        return root.parent
    return root


def select_windhawk_installer_asset(release: dict[str, Any]) -> tuple[str, str]:
    assets = [
        asset for asset in (release.get("assets") or [])
        if isinstance(asset, dict)
    ]

    exact = [
        asset for asset in assets
        if str(asset.get("name", "")).lower() == WINDHAWK_INSTALLER_ASSET
    ]
    fallback = [
        asset for asset in assets
        if str(asset.get("name", "")).lower().endswith(".exe")
        and "setup" in str(asset.get("name", "")).lower()
        and "offline" not in str(asset.get("name", "")).lower()
    ]

    for asset in exact + fallback:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name and url:
            return name, url

    available = ", ".join(
        str(asset.get("name", ""))
        for asset in assets
        if asset.get("name")
    ) or "none"
    raise WindhawkBarError(
        f"Could not find a Windhawk installer asset in the latest release. "
        f"Available assets: {available}"
    )


def latest_windhawk_installer() -> tuple[str, str, str]:
    try:
        release = request_json(WINDHAWK_RELEASES_API)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise WindhawkBarError(f"Failed to query latest Windhawk release: {exc}") from exc

    if not isinstance(release, dict):
        raise WindhawkBarError("Unexpected response from the Windhawk releases API.")

    tag = str(release.get("tag_name") or release.get("name") or "latest")
    name, url = select_windhawk_installer_asset(release)
    return tag, name, url


def run_windhawk_installer(installer_path: Path, root: Path, portable_install: bool) -> None:
    mode_arg = "/PORTABLE" if portable_install else "/STANDARD"
    command = [str(installer_path), "/S", mode_arg]
    if portable_install:
        install_dir = windhawk_portable_install_dir(root)
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WindhawkBarError(
                f"Failed to create portable Windhawk install directory {install_dir}: {exc}"
            ) from exc
        command.append(f"/D={install_dir}")

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise WindhawkBarError(f"Failed to launch Windhawk installer: {exc}") from exc
    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        detail = f": {output}" if output else ""
        raise WindhawkBarError(
            f"Windhawk installer failed with exit code {completed.returncode}{detail}"
        )


def wait_for_installed_windhawk_root(root: Path, portable_install: bool) -> Path:
    deadline = time.time() + 30
    while True:
        detected = find_detected_windhawk_root(root, portable_install)
        if detected is not None:
            return detected
        if time.time() >= deadline:
            break
        time.sleep(1)

    candidates = ", ".join(str(p) for p in windhawk_root_candidates(root, portable_install))
    raise WindhawkBarError(
        "Windhawk was installed, but the Windhawk data path was not detected. "
        f"Checked: {candidates}"
    )


def install_latest_windhawk(root: Path, portable_install: bool, dry_run: bool) -> Path:
    install_type = "portable" if portable_install else "standard"

    if dry_run:
        print(
            f"Would download the latest Windhawk installer from {WINDHAWK_RELEASES_PAGE} "
            f"and run it as a {install_type} install."
        )
        return root

    if os.name != "nt":
        raise WindhawkBarError("Windhawk auto-install is only supported on Windows.")

    if not portable_install and not is_admin():
        raise WindhawkBarError(
            "Auto-installing standard Windhawk requires an elevated terminal."
        )

    tag, asset_name, asset_url = latest_windhawk_installer()

    with tempfile.TemporaryDirectory(prefix="windhawkbar_install_") as temp_dir:
        installer_path = Path(temp_dir) / asset_name
        print(f"Downloading Windhawk {tag} installer: {asset_url}")
        try:
            download_file(asset_url, installer_path)
        except (OSError, urllib.error.URLError) as exc:
            raise WindhawkBarError(f"Failed to download Windhawk installer: {exc}") from exc

        print(f"Installing Windhawk {tag} ({install_type})...")
        run_windhawk_installer(installer_path, root, portable_install)

    detected_root = wait_for_installed_windhawk_root(root, portable_install)
    print(f"Windhawk detected at: {detected_root}")
    return detected_root


def choose_windhawk_install_portable(args: argparse.Namespace, backup: dict[str, Any]) -> bool:
    if args.portable is not None:
        return bool(args.portable)
    if isinstance(backup.get("portable"), bool):
        return bool(backup["portable"])
    return False


def ensure_windhawk_root_for_restore(
    root: Path,
    args: argparse.Namespace,
    backup: dict[str, Any],
) -> tuple[Path, bool | None]:
    portable_install = choose_windhawk_install_portable(args, backup)
    detected = find_detected_windhawk_root(root, portable_install)
    if detected is not None:
        return detected, None

    if not args.install_windhawk_if_missing:
        validate_windhawk_root(root)
        return root, None

    print(f"Windhawk was not detected at: {root}")
    installed_root = install_latest_windhawk(root, portable_install, args.dry_run)
    if args.dry_run:
        return installed_root, portable_install
    return installed_root, portable_install


def read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def copy_project_files(stage_dir: Path) -> None:
    project_dir = Path(__file__).resolve().parent
    for name in ("windhawk_bar.py", "README.md"):
        src = project_dir / name
        if src.is_file():
            shutil.copy2(src, stage_dir / name)


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            archive_name = path.relative_to(source_dir).as_posix()
            if path.is_dir():
                zf.write(path, archive_name + "/")
            else:
                zf.write(path, archive_name)


def extract_zip_safe(zip_path: Path, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            destination = (target_root / member.filename).resolve()
            try:
                destination.relative_to(target_root)
            except ValueError:
                raise WindhawkBarError(f"Unsafe zip entry: {member.filename}")
            zf.extract(member, target_root)


def find_backup_json(base_dir: Path) -> Path:
    direct = base_dir / "backup.json"
    if direct.is_file():
        return direct

    matches = [p for p in base_dir.rglob("backup.json") if p.is_file()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise WindhawkBarError(f"backup.json not found in {base_dir}")
    raise WindhawkBarError(f"Multiple backup.json files found in {base_dir}")


def read_ini(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    if not path.exists():
        return cp

    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding) as fh:
                cp.read_file(fh)
            return cp
        except UnicodeError:
            continue

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        cp.read_file(fh)
    return cp


def write_ini(path: Path, cp: configparser.ConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-16") as fh:
        cp.write(fh, space_around_delimiters=False)


def ini_section_to_typed_values(cp: configparser.ConfigParser, section: str) -> dict[str, dict[str, Any]]:
    if not cp.has_section(section):
        return {}
    return {
        key: {"type": "INI", "value": value}
        for key, value in cp.items(section)
    }


def set_ini_typed_values(cp: configparser.ConfigParser, section: str, values: dict[str, dict[str, Any]]) -> None:
    if not cp.has_section(section):
        cp.add_section(section)
    for key, typed in values.items():
        cp.set(section, key, str(typed.get("value", "")))


def typed_simple_value(typed: dict[str, Any] | None, default: Any = "") -> Any:
    if not typed:
        return default
    return typed.get("value", default)


def set_typed_value(values: dict[str, dict[str, Any]], key: str, value: Any, value_type: str | None = None) -> None:
    if value_type is None:
        value_type = "REG_DWORD" if isinstance(value, int) else "REG_SZ"
    values[key] = {"type": value_type, "value": value}


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def registry_available() -> None:
    if winreg is None:
        raise WindhawkBarError("The Windows registry API is not available.")


def read_reg_values(subkey: str) -> dict[str, dict[str, Any]]:
    registry_available()
    values: dict[str, dict[str, Any]] = {}
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            subkey,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
    except OSError:
        return values

    try:
        index = 0
        while True:
            try:
                name, value, reg_type = winreg.EnumValue(key, index)
            except OSError:
                break
            if reg_type == winreg.REG_BINARY:
                value = value.hex()
            values[name] = {
                "type": REG_TYPE_NAMES.get(reg_type, f"REG_{reg_type}"),
                "value": value,
            }
            index += 1
    finally:
        winreg.CloseKey(key)

    return values


def enum_reg_subkeys(subkey: str) -> list[str]:
    registry_available()
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            subkey,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
    except OSError:
        return []

    names: list[str] = []
    try:
        index = 0
        while True:
            try:
                names.append(winreg.EnumKey(key, index))
            except OSError:
                break
            index += 1
    finally:
        winreg.CloseKey(key)
    return names


def write_reg_values(subkey: str, values: dict[str, dict[str, Any]], dry_run: bool) -> None:
    registry_available()
    if dry_run:
        print(f"Would write registry key HKLM\\{subkey}")
        return

    key = winreg.CreateKeyEx(
        winreg.HKEY_LOCAL_MACHINE,
        subkey,
        0,
        winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
    )
    try:
        for name, typed in values.items():
            reg_type_name = typed.get("type", "REG_SZ")
            reg_type = REG_TYPES_BY_NAME.get(reg_type_name)
            if reg_type is None:
                print(f"Warning: skipping unsupported registry type for {name}: {reg_type_name}")
                continue
            value = typed.get("value")
            if reg_type == winreg.REG_BINARY and isinstance(value, str):
                value = bytes.fromhex(value)
            winreg.SetValueEx(key, name, 0, reg_type, value)
    finally:
        winreg.CloseKey(key)


def delete_reg_tree(subkey: str, dry_run: bool) -> None:
    registry_available()
    if dry_run:
        print(f"Would delete registry tree HKLM\\{subkey}")
        return
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, subkey, winreg.KEY_WOW64_64KEY, 0)
    except OSError:
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, subkey)
        except OSError:
            pass


def current_settings_change_time() -> int:
    return int(time.time()) & 0x7FFFFFFF


class Storage:
    def __init__(self, root: Path, portable: bool):
        self.root = root
        self.portable = portable

    def list_mod_ids(self) -> list[str]:
        if self.portable:
            mods_dir = self.root / "Engine" / "Mods"
            return sorted(p.stem for p in mods_dir.glob("*.ini") if p.is_file())
        return sorted(enum_reg_subkeys(REG_BASE + r"\Engine\Mods"))

    def read_mod_config(self, mod_id: str) -> dict[str, dict[str, Any]]:
        checked_mod_id(mod_id)
        if self.portable:
            cp = read_ini(self.root / "Engine" / "Mods" / f"{mod_id}.ini")
            return ini_section_to_typed_values(cp, "Mod")
        return read_reg_values(REG_BASE + rf"\Engine\Mods\{mod_id}")

    def read_mod_settings(self, mod_id: str) -> dict[str, dict[str, Any]]:
        checked_mod_id(mod_id)
        if self.portable:
            cp = read_ini(self.root / "Engine" / "Mods" / f"{mod_id}.ini")
            return ini_section_to_typed_values(cp, "Settings")
        return read_reg_values(REG_BASE + rf"\Engine\Mods\{mod_id}\Settings")

    def write_mod_config(self, mod_id: str, config: dict[str, dict[str, Any]], dry_run: bool) -> None:
        checked_mod_id(mod_id)
        if self.portable:
            path = self.root / "Engine" / "Mods" / f"{mod_id}.ini"
            if dry_run:
                print(f"Would write INI config: {path}")
                return
            cp = read_ini(path)
            set_ini_typed_values(cp, "Mod", config)
            write_ini(path, cp)
            return

        write_reg_values(REG_BASE + rf"\Engine\Mods\{mod_id}", config, dry_run)

    def write_mod_settings(self, mod_id: str, settings: dict[str, dict[str, Any]], dry_run: bool) -> None:
        checked_mod_id(mod_id)
        if self.portable:
            path = self.root / "Engine" / "Mods" / f"{mod_id}.ini"
            if dry_run:
                print(f"Would write INI settings: {path}")
                return
            cp = read_ini(path)
            if cp.has_section("Settings"):
                cp.remove_section("Settings")
            set_ini_typed_values(cp, "Settings", settings)
            if not cp.has_section("Mod"):
                cp.add_section("Mod")
            cp.set("Mod", "SettingsChangeTime", str(current_settings_change_time()))
            write_ini(path, cp)
            return

        settings_subkey = REG_BASE + rf"\Engine\Mods\{mod_id}\Settings"
        delete_reg_tree(settings_subkey, dry_run)
        write_reg_values(settings_subkey, settings, dry_run)
        write_reg_values(
            REG_BASE + rf"\Engine\Mods\{mod_id}",
            {"SettingsChangeTime": {"type": "REG_DWORD", "value": current_settings_change_time()}},
            dry_run,
        )

    def read_app_settings(self) -> dict[str, dict[str, dict[str, Any]]]:
        if self.portable:
            return {
                "Settings": ini_section_to_typed_values(read_ini(self.root / "settings.ini"), "Settings"),
                "Engine/Settings": ini_section_to_typed_values(read_ini(self.root / "Engine" / "settings.ini"), "Settings"),
            }
        return {
            "Settings": read_reg_values(REG_BASE + r"\Settings"),
            "Engine/Settings": read_reg_values(REG_BASE + r"\Engine\Settings"),
        }

    def write_app_settings(self, settings: dict[str, dict[str, dict[str, Any]]], dry_run: bool) -> None:
        if self.portable:
            targets = {
                "Settings": self.root / "settings.ini",
                "Engine/Settings": self.root / "Engine" / "settings.ini",
            }
            for section_name, path in targets.items():
                values = settings.get(section_name, {})
                if dry_run:
                    print(f"Would write app settings INI: {path}")
                    continue
                cp = read_ini(path)
                set_ini_typed_values(cp, "Settings", values)
                write_ini(path, cp)
            return

        write_reg_values(REG_BASE + r"\Settings", settings.get("Settings", {}), dry_run)
        write_reg_values(REG_BASE + r"\Engine\Settings", settings.get("Engine/Settings", {}), dry_run)


def read_userprofile(root: Path) -> dict[str, Any]:
    path = root / "userprofile.json"
    if not path.exists():
        return {}
    try:
        return read_json_file(path)
    except (OSError, json.JSONDecodeError):
        return {}


def write_userprofile(root: Path, backup_profile: dict[str, Any], mods: list[dict[str, Any]], dry_run: bool) -> None:
    path = root / "userprofile.json"
    current = read_userprofile(root)
    current.setdefault("app", {})
    current.setdefault("mods", {})

    backup_mods = backup_profile.get("mods", {}) if isinstance(backup_profile, dict) else {}
    for mod in mods:
        mod_id = mod["id"]
        current_mod = current["mods"].get(mod_id, {})
        backup_mod = backup_mods.get(mod_id, {})
        if isinstance(backup_mod, dict) and "rating" in backup_mod:
            current_mod["rating"] = backup_mod["rating"]
        if "restored_version" in mod:
            current_mod["version"] = mod["restored_version"]
            current_mod.pop("latestVersion", None)
        disabled = mod.get("restored_disabled")
        if disabled is not None:
            if disabled:
                current_mod["disabled"] = True
            else:
                current_mod.pop("disabled", None)
        current["mods"][mod_id] = current_mod

    if dry_run:
        print(f"Would update userprofile: {path}")
        return
    write_json_file(path, current)


def copy_asset(src: Path, backup_dir: Path, relative_asset_path: str) -> str:
    dst = backup_dir / relative_asset_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return relative_asset_path.replace("\\", "/")


def backup_mod_assets(root: Path, backup_dir: Path, mod_id: str, config: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stem = safe_asset_stem(mod_id)
    assets: dict[str, Any] = {"compiled": []}

    source_path = root / "ModsSource" / f"{mod_id}.wh.cpp"
    if source_path.is_file():
        assets["source"] = copy_asset(source_path, backup_dir, f"assets/sources/{stem}.wh.cpp")

    dll_name = typed_simple_value(config.get("LibraryFileName"))
    if isinstance(dll_name, str) and dll_name:
        for subfolder in ("32", "64", "arm64"):
            dll_path = root / "Engine" / "Mods" / subfolder / dll_name
            if dll_path.is_file():
                assets["compiled"].append({
                    "arch": subfolder,
                    "file_name": dll_name,
                    "path": copy_asset(dll_path, backup_dir, f"assets/compiled/{subfolder}/{dll_name}"),
                })

    return assets


def build_backup(args: argparse.Namespace) -> None:
    root = expand_path(args.windhawk_root)
    validate_windhawk_root(root)
    portable = detect_portable(root, args.portable)

    output_zip = resolve_backup_zip_path(args.output)
    temp_zip = output_zip.with_name(output_zip.name + ".tmp")

    with tempfile.TemporaryDirectory(prefix="windhawkbar_stage_") as temp_dir:
        backup_dir = Path(temp_dir) / "backup"
        (backup_dir / "assets").mkdir(parents=True)

        storage = Storage(root, portable)
        mod_ids = storage.list_mod_ids()

        backup: dict[str, Any] = {
            "format": FORMAT_VERSION,
            "tool": APP_NAME,
            "created": utc_now_iso(),
            "windhawk_root": str(root),
            "portable": portable,
            "mods_url_root": MODS_URL_ROOT,
            "app_settings": storage.read_app_settings(),
            "userprofile": read_userprofile(root),
            "mods": [],
        }

        for mod_id in mod_ids:
            config = storage.read_mod_config(mod_id)
            settings = storage.read_mod_settings(mod_id)
            assets = backup_mod_assets(root, backup_dir, mod_id, config)

            metadata: dict[str, Any] = {}
            if assets.get("source"):
                source_text = (backup_dir / assets["source"]).read_text(encoding="utf-8", errors="replace")
                metadata = extract_mod_metadata(source_text)

            backup["mods"].append({
                "id": mod_id,
                "kind": "local" if mod_id.startswith("local@") else "repository",
                "metadata": metadata,
                "config": config,
                "settings": settings,
                "assets": assets,
            })

        write_json_file(backup_dir / "backup.json", backup)
        copy_project_files(backup_dir)
        zip_directory(backup_dir, temp_zip)
        temp_zip.replace(output_zip)

    print(f"Backup created: {output_zip}")
    print(f"Mods recorded: {len(backup['mods'])}")


@contextmanager
def open_backup(path_arg: str | Path):
    path = expand_path(path_arg)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    if path.is_dir():
        backup_json = find_backup_json(path)
    else:
        if path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="windhawkbar_restore_")
            extracted_dir = Path(temp_dir.name)
            extract_zip_safe(path, extracted_dir)
            backup_json = find_backup_json(extracted_dir)
        else:
            backup_json = path

    backup_dir = backup_json.parent

    backup = read_json_file(backup_json)
    if backup.get("format") != FORMAT_VERSION:
        raise WindhawkBarError(f"Unsupported backup format: {backup.get('format')}")

    try:
        yield backup_dir, backup
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def asset_path(backup_dir: Path, asset_rel: str | None) -> Path | None:
    if not asset_rel:
        return None
    path = (backup_dir / asset_rel).resolve()
    try:
        path.relative_to(backup_dir.resolve())
    except ValueError:
        raise WindhawkBarError(f"Asset path escapes backup directory: {asset_rel}")
    return path


def archived_restore(root: Path, backup_dir: Path, storage: Storage, mod: dict[str, Any], dry_run: bool) -> None:
    mod_id = checked_mod_id(mod["id"])
    assets = mod.get("assets", {})

    source_asset = asset_path(backup_dir, assets.get("source"))
    if source_asset and source_asset.is_file():
        target = root / "ModsSource" / f"{mod_id}.wh.cpp"
        if dry_run:
            print(f"Would restore source asset: {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_asset, target)

    for compiled in assets.get("compiled", []):
        compiled_asset = asset_path(backup_dir, compiled.get("path"))
        if not compiled_asset or not compiled_asset.is_file():
            print(f"Warning: missing compiled asset for {mod_id}: {compiled.get('path')}")
            continue
        target = root / "Engine" / "Mods" / compiled["arch"] / compiled["file_name"]
        if dry_run:
            print(f"Would restore compiled asset: {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(compiled_asset, target)

    storage.write_mod_config(mod_id, dict(mod.get("config", {})), dry_run)
    storage.write_mod_settings(mod_id, dict(mod.get("settings", {})), dry_run)

    version = typed_simple_value(mod.get("config", {}).get("Version"), "")
    disabled = bool(coerce_int(typed_simple_value(mod.get("config", {}).get("Disabled"), 0)))
    mod["restored_version"] = version
    mod["restored_disabled"] = disabled


def install_repository_latest(
    root: Path,
    storage: Storage,
    mod: dict[str, Any],
    arm64_enabled: bool,
    dry_run: bool,
) -> None:
    mod_id = checked_mod_id(mod["id"])
    source_url = mod_latest_source_url(mod_id)
    print(f"Fetching latest source for {mod_id}")
    source = normalize_source_newlines(request_text(source_url))
    metadata = extract_mod_metadata(source)

    if metadata.get("id") != mod_id:
        raise WindhawkBarError(
            f"Downloaded source id mismatch for {mod_id}: {metadata.get('id')!r}"
        )

    version = str(metadata.get("version") or "")
    if not version:
        raise WindhawkBarError(f"Latest source for {mod_id} has no version")

    architectures = list(metadata.get("architecture") or [])
    subfolders = architecture_subfolders(architectures, arm64_enabled)
    target_dll_name = random_dll_name(mod_id, version)

    if dry_run:
        print(f"Would download {mod_id} {version} DLLs for: {', '.join(subfolders)}")
    else:
        for subfolder in subfolders:
            url = mod_dll_url(mod_id, version, subfolder)
            target = root / "Engine" / "Mods" / subfolder / target_dll_name
            print(f"Downloading {url}")
            data = request_bytes(url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

        source_target = root / "ModsSource" / f"{mod_id}.wh.cpp"
        source_target.parent.mkdir(parents=True, exist_ok=True)
        source_target.write_text(source, encoding="utf-8", newline="")

    old_config = dict(mod.get("config", {}))
    disabled = coerce_int(typed_simple_value(old_config.get("Disabled"), 0))
    new_config = {
        key: value
        for key, value in old_config.items()
        if key not in REPOSITORY_CONFIG_FIELDS
    }
    set_typed_value(new_config, "LibraryFileName", target_dll_name)
    set_typed_value(new_config, "Disabled", disabled, "REG_DWORD")
    set_typed_value(new_config, "Include", metadata_pipe_list(metadata, "include"))
    set_typed_value(new_config, "Exclude", metadata_pipe_list(metadata, "exclude"))
    set_typed_value(new_config, "Architecture", metadata_pipe_list(metadata, "architecture"))
    set_typed_value(new_config, "Version", version)

    storage.write_mod_config(mod_id, new_config, dry_run)
    storage.write_mod_settings(mod_id, dict(mod.get("settings", {})), dry_run)
    delete_old_mod_dlls(root, mod_id, target_dll_name, subfolders, dry_run)

    mod["restored_version"] = version
    mod["restored_disabled"] = bool(disabled)


def restore_backup(args: argparse.Namespace) -> None:
    root = expand_path(args.windhawk_root)
    with open_backup(args.backup) as (backup_dir, backup):
        root, installed_portable = ensure_windhawk_root_for_restore(root, args, backup)
        portable_override = args.portable
        if portable_override is None and installed_portable is not None:
            portable_override = installed_portable
        portable = detect_portable(root, portable_override)
        storage = Storage(root, portable)
        asset_fallback = args.asset_fallback and not args.json_only

        if not portable and not args.dry_run and not is_admin():
            raise WindhawkBarError("Restoring a standard install requires an elevated terminal.")

        if backup.get("portable") != portable:
            print(
                "Warning: backup portable mode differs from target mode "
                f"(backup={backup.get('portable')}, target={portable})."
            )

        service_started = False
        if args.manage_service and not portable and not args.dry_run:
            stop_service()
            service_started = True

        mods = list(backup.get("mods", []))
        restored_mods: list[dict[str, Any]] = []
        skipped: list[str] = []
        failures: list[str] = []
        try:
            if args.restore_app_settings:
                storage.write_app_settings(dict(backup.get("app_settings", {})), args.dry_run)

            for mod in mods:
                mod_id = mod.get("id")
                if not isinstance(mod_id, str):
                    continue

                if args.json_only and (
                    mod_id.startswith("local@")
                    or mod.get("kind") == "local"
                ):
                    reason = "local mods require archived assets"
                    print(f"Skipping {mod_id}: {reason} in --json-only mode.")
                    skipped.append(f"{mod_id}: {reason}")
                    continue

                use_archive = (
                    args.offline
                    or mod_id.startswith("local@")
                    or mod.get("kind") == "local"
                )

                try:
                    if use_archive:
                        print(f"Restoring {mod_id} from assets")
                        archived_restore(root, backup_dir, storage, mod, args.dry_run)
                    else:
                        install_repository_latest(root, storage, mod, args.arm64, args.dry_run)
                    restored_mods.append(mod)
                except (OSError, urllib.error.URLError, WindhawkBarError) as exc:
                    if asset_fallback and not use_archive:
                        print(f"Warning: online restore failed for {mod_id}; falling back to assets: {exc}")
                        archived_restore(root, backup_dir, storage, mod, args.dry_run)
                        restored_mods.append(mod)
                    else:
                        failures.append(f"{mod_id}: {exc}")

            profile_mods = restored_mods if args.json_only else mods
            write_userprofile(root, dict(backup.get("userprofile", {})), profile_mods, args.dry_run)
        finally:
            if service_started:
                start_service()

        if skipped:
            print("\nSkipped:")
            for item in skipped:
                print(f"  - {item}")

        if failures:
            print("\nFailures:")
            for failure in failures:
                print(f"  - {failure}")
            raise SystemExit(1)

    print("Restore complete." if not args.dry_run else "Dry run complete.")


def list_backup(args: argparse.Namespace) -> None:
    with open_backup(args.backup) as (_, backup):
        print(f"Created: {backup.get('created')}")
        print(f"Portable: {backup.get('portable')}")
        print(f"Mods: {len(backup.get('mods', []))}")
        for mod in backup.get("mods", []):
            config = mod.get("config", {})
            version = typed_simple_value(config.get("Version"), mod.get("metadata", {}).get("version", ""))
            disabled = coerce_int(typed_simple_value(config.get("Disabled"), 0))
            kind = mod.get("kind", "repository")
            print(f"  - {mod.get('id')}  version={version or '-'}  kind={kind}  disabled={bool(disabled)}")


def add_common_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--windhawk-root",
        default=str(DEFAULT_WINDHAWK_ROOT),
        help="Windhawk data path. Default: %%ProgramData%%\\Windhawk",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--portable", dest="portable", action="store_true", help="Use portable INI storage.")
    mode.add_argument("--standard", dest="portable", action="store_false", help="Use standard HKLM registry storage.")
    parser.set_defaults(portable=None)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="windhawk_bar.py", description="JSON/assets backup and restore for Windhawk.")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="Create a JSON/assets backup.")
    add_common_target_args(backup)
    backup.add_argument(
        "--output",
        default=BACKUP_ZIP_NAME,
        help=f"Output zip path or folder. Default: {BACKUP_ZIP_NAME}",
    )
    backup.set_defaults(func=build_backup)

    restore = sub.add_parser("restore", help="Restore a backup.")
    add_common_target_args(restore)
    restore.add_argument("backup", help="Backup zip, backup directory, or backup.json path.")
    restore.add_argument("--dry-run", action="store_true", help="Print intended actions without writing files or registry.")
    restore_mode = restore.add_mutually_exclusive_group()
    restore_mode.add_argument("--offline", action="store_true", help="Restore all mods from archived assets.")
    restore_mode.add_argument(
        "--json-only",
        action="store_true",
        help=(
            "Restore using only backup.json. Catalog mods are downloaded, "
            "asset fallback is disabled, and local mods are skipped."
        ),
    )
    restore.add_argument(
        "--no-asset-fallback",
        dest="asset_fallback",
        action="store_false",
        help="Fail instead of using archived assets if online catalog restore fails.",
    )
    restore.add_argument("--arm64", action="store_true", default=host_arm64_enabled(), help="Also restore/download ARM64 DLLs when metadata allows it.")
    restore.add_argument("--no-service", dest="manage_service", action="store_false", help="Do not stop/start the Windhawk service.")
    restore.add_argument(
        "--install-windhawk-if-missing",
        action="store_true",
        help="Download and silently install the latest Windhawk release if the target data path is not detected.",
    )
    restore.add_argument("--restore-app-settings", action="store_true", help="Restore backed-up app and engine settings.")
    restore.set_defaults(func=restore_backup, manage_service=True, asset_fallback=True)

    list_cmd = sub.add_parser("list", help="List backup contents.")
    list_cmd.add_argument("backup", help="Backup zip, backup directory, or backup.json path.")
    list_cmd.set_defaults(func=list_backup)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        args.func(args)
        return 0
    except WindhawkBarError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
