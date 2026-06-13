#!/usr/bin/env python3
"""Download and install the latest x64 7-Zip Zstandard build from GitHub."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


LATEST_RELEASE_API = "https://api.github.com/repos/mcmilk/7-Zip-zstd/releases/latest"
ASSET_SUFFIX = "zstd-x64.exe"
USER_AGENT = "Alchemy-7zip-zstd-installer/1.0"


class InstallError(RuntimeError):
    pass


def request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise InstallError(f"GitHub API request failed: HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise InstallError(f"GitHub API request failed: {exc.reason}") from exc


def find_x64_installer_asset(release: dict) -> tuple[str, str]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise InstallError("Latest release response did not contain an assets list.")

    matches = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue

        name = asset.get("name")
        download_url = asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and isinstance(download_url, str)
            and name.lower().endswith(ASSET_SUFFIX)
        ):
            matches.append((name, download_url))

    if not matches:
        names = sorted(
            asset.get("name")
            for asset in assets
            if isinstance(asset, dict) and isinstance(asset.get("name"), str)
        )
        asset_list = "\n".join(f"  - {name}" for name in names) or "  (none)"
        raise InstallError(
            f'Could not find a release asset ending with "{ASSET_SUFFIX}".\n'
            f"Assets in latest release:\n{asset_list}"
        )

    return matches[0]


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with destination.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
    except urllib.error.HTTPError as exc:
        raise InstallError(f"Download failed: HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise InstallError(f"Download failed: {exc.reason}: {url}") from exc
    except OSError as exc:
        raise InstallError(f'Could not write installer to "{destination}": {exc}') from exc


def run_installer(installer_path: Path, installer_args: list[str]) -> int:
    command = [str(installer_path), *installer_args]
    print(f"Running: {' '.join(command)}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the latest 7-Zip Zstandard x64 installer from GitHub "
            "and run it."
        )
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="run the installer UI instead of passing the silent /S switch",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the downloaded installer in the temp directory",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="download the installer but do not run it",
    )
    parser.add_argument(
        "installer_args",
        nargs=argparse.REMAINDER,
        help="extra arguments to pass to the installer after --",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    extra_installer_args = args.installer_args
    if extra_installer_args[:1] == ["--"]:
        extra_installer_args = extra_installer_args[1:]

    try:
        print("Checking latest 7-Zip Zstandard release...")
        release = request_json(LATEST_RELEASE_API)
        tag_name = release.get("tag_name", "latest")
        asset_name, download_url = find_x64_installer_asset(release)

        installer_path = Path(tempfile.gettempdir()) / asset_name
        print(f"Latest release: {tag_name}")
        print(f"Downloading: {asset_name}")
        download_file(download_url, installer_path)
        print(f"Downloaded to: {installer_path}")

        if args.download_only:
            return 0

        installer_args = [] if args.interactive else ["/S"]
        installer_args.extend(extra_installer_args)
        result = run_installer(installer_path, installer_args)

        if not args.keep:
            try:
                installer_path.unlink(missing_ok=True)
            except OSError as exc:
                print(f'Warning: could not delete "{installer_path}": {exc}', file=sys.stderr)

        return result
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except InstallError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if os.name != "nt":
        print("Error: this installer script is intended for Windows.", file=sys.stderr)
        sys.exit(1)

    sys.exit(main())
