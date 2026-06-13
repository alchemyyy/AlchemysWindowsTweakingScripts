#!/usr/bin/env python3
"""Install Vencord and apply preferred local settings."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


INSTALLER_URL = "https://github.com/Vencord/Installer/releases/latest/download/VencordInstallerCli.exe"
THEME_PAGE_URL = "https://codeberg.org/ridge/Discord-Adblock/src/branch/main/discord-adblock.css"
THEME_RAW_URL = "https://codeberg.org/ridge/Discord-Adblock/raw/branch/main/discord-adblock.css"
THEME_FILE_NAME = "discord-adblock.css"

PLUGINS_TO_ENABLE = [
    "ChatInputButtonAPI",
    "CommandsAPI",
    "DynamicImageModalAPI",
    "MemberListDecoratorsAPI",
    "MessageAccessoriesAPI",
    "MessageDecorationsAPI",
    "MessageEventsAPI",
    "MessageUpdaterAPI",
    "ServerListAPI",
    "UserSettingsAPI",
    "AccountPanelServerProfile",
    "AlwaysTrust",
    "BetterSettings",
    "BiggerStreamPreview",
    "CallTimer",
    "ClearURLs",
    "CopyFileContents",
    "CrashHandler",
    "DisableCallIdle",
    "FakeNitro",
    "FixCodeblockGap",
    "FixImagesQuality",
    "FixSpotifyEmbeds",
    "ForceOwnerCrown",
    "FullSearchContext",
    "GreetStickerPicker",
    "ImageZoom",
    "ImplicitRelationships",
    "MemberCount",
    "MessageLogger",
    "NoOnboardingDelay",
    "NoPendingCount",
    "NormalizeMessageLinks",
    "PermissionFreeWill",
    "PermissionsViewer",
    "ReadAllNotificationsButton",
    "RelationshipNotifier",
    "ServerInfo",
    "ShowHiddenChannels",
    "ShowHiddenThings",
    "SilentMessageToggle",
    "SilentTyping",
    "SpotifyCrack",
    "TypingIndicator",
    "Unindent",
    "ValidReply",
    "ValidUser",
    "BadgeAPI",
    "NoTrack",
    "Settings",
    "SupportHelper",
]


class SetupError(RuntimeError):
    """Raised for expected setup failures with user-readable messages."""


def log(message: str) -> None:
    print(f"[setup_vencord] {message}")


def download(urls: Iterable[str], destination: Path, *, expect_css: bool = False) -> None:
    headers = {
        "User-Agent": "setup_vencord.py (urllib)",
        "Accept": "text/css,*/*;q=0.8" if expect_css else "*/*",
    }

    last_error: Exception | None = None
    for url in urls:
        try:
            log(f"Downloading {url}")
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()

            if expect_css:
                sample = data[:512].lstrip().lower()
                content_type = response.headers.get("Content-Type", "")
                if sample.startswith(b"<!doctype") or sample.startswith(b"<html") or "text/html" in content_type:
                    raise SetupError(f"Downloaded HTML instead of CSS from {url}")

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            log(f"Saved {destination}")
            return
        except (OSError, urllib.error.URLError, SetupError) as exc:
            last_error = exc
            log(f"Download failed: {exc}")

    raise SetupError(f"Could not download {destination.name}: {last_error}")


def run_installer(installer_path: Path, branch: str, location: str | None) -> None:
    command = [str(installer_path), "--install"]
    if location:
        command.extend(["--location", location])
    else:
        command.extend(["--branch", branch])

    log("Running Vencord installer")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SetupError(f"Vencord installer exited with code {result.returncode}")


def get_vencord_data_dir() -> Path:
    vencord_user_data_dir = os.environ.get("VENCORD_USER_DATA_DIR")
    if vencord_user_data_dir:
        return Path(vencord_user_data_dir).expanduser()

    discord_user_data_dir = os.environ.get("DISCORD_USER_DATA_DIR")
    if discord_user_data_dir:
        return Path(discord_user_data_dir).expanduser().parent / "VencordData"

    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SetupError("APPDATA is not set; cannot determine the Vencord settings folder")

    return Path(appdata) / "Vencord"


def read_settings(settings_file: Path) -> dict:
    if not settings_file.exists():
        return {}

    try:
        with settings_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        backup = settings_file.with_suffix(f".invalid-{time.strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(settings_file, backup)
        raise SetupError(f"{settings_file} is not valid JSON. Backed it up to {backup}") from exc

    if not isinstance(data, dict):
        raise SetupError(f"{settings_file} must contain a JSON object")

    return data


def write_settings(settings_file: Path, settings: dict) -> None:
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if settings_file.exists():
        backup = settings_file.with_suffix(f".bak-{time.strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(settings_file, backup)
        log(f"Backed up existing settings to {backup}")

    with settings_file.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(settings, handle, indent=4)
        handle.write("\n")

    log(f"Updated {settings_file}")


def ensure_string_list(settings: dict, key: str) -> list[str]:
    value = settings.get(key)
    if isinstance(value, list):
        cleaned = [item for item in value if isinstance(item, str)]
    else:
        cleaned = []

    settings[key] = cleaned
    return cleaned


def apply_vencord_settings(settings_file: Path) -> None:
    settings = read_settings(settings_file)

    settings["useQuickCss"] = True

    enabled_themes = ensure_string_list(settings, "enabledThemes")
    if THEME_FILE_NAME not in enabled_themes:
        enabled_themes.append(THEME_FILE_NAME)

    if "themeLinks" not in settings or not isinstance(settings["themeLinks"], list):
        settings["themeLinks"] = []

    plugins = settings.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        settings["plugins"] = plugins

    for plugin_name in PLUGINS_TO_ENABLE:
        plugin_settings = plugins.get(plugin_name)
        if not isinstance(plugin_settings, dict):
            plugin_settings = {}
            plugins[plugin_name] = plugin_settings
        plugin_settings["enabled"] = True

    write_settings(settings_file, settings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Vencord and apply preferred settings.")
    parser.add_argument(
        "--branch",
        choices=("auto", "stable", "ptb", "canary"),
        default="auto",
        help="Discord branch to patch when --location is not supplied. Default: auto",
    )
    parser.add_argument(
        "--location",
        help="Explicit Discord install folder to patch, for example %%LOCALAPPDATA%%\\Discord",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Only update the Vencord settings and theme file.",
    )
    return parser.parse_args()


def main() -> int:
    if os.name != "nt":
        raise SetupError("This script is intended for Windows because it downloads the Windows Vencord installer")

    args = parse_args()
    data_dir = get_vencord_data_dir()
    themes_dir = data_dir / "themes"
    settings_file = data_dir / "settings" / "settings.json"

    log(f"Using Vencord data directory: {data_dir}")

    if not args.skip_install:
        installer_path = Path(tempfile.gettempdir()) / "VencordInstallerCli.exe"
        download([INSTALLER_URL], installer_path)
        run_installer(installer_path, args.branch, args.location)

    download([THEME_RAW_URL, THEME_PAGE_URL], themes_dir / THEME_FILE_NAME, expect_css=True)
    apply_vencord_settings(settings_file)

    log("Done. Start or restart Discord for the changes to load.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
