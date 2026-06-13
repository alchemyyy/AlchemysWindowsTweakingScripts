from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from .ico import IcoFile
from .install import find_install_dir, looks_like_install_dir
from .patcher import (
    backup_files,
    build_patch_plans,
    find_patch_targets,
    is_admin,
    make_backup_dir,
    patch_file,
    refresh_shell_icons,
    restore_backup,
)
from .processes import close_locking_processes, get_locking_processes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Patch installed 7-Zip Zstandard icon resources in-place."
    )
    parser.add_argument("--install-dir", type=Path, help="Installed 7-Zip Zstandard directory.")
    parser.add_argument(
        "--icon",
        type=Path,
        default=_default_icon_path(),
        help="ICO file to write into resources. Defaults to bundled 7zip-box.ico.",
    )
    parser.add_argument(
        "--target",
        action="append",
        help="Specific target file, relative to install-dir or absolute. May be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect targets without patching.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backups before patching.")
    parser.add_argument("--no-refresh", action="store_true", help="Do not notify Explorer after patching.")
    parser.add_argument(
        "--no-kill-locks",
        action="store_true",
        help="Do not close or force-kill processes that lock target binaries.",
    )
    parser.add_argument(
        "--no-restart-explorer",
        action="store_true",
        help="Do not restart Explorer if it had to be closed.",
    )
    parser.add_argument("--restore", action="store_true", help="Restore the latest backup and exit.")
    parser.add_argument("--backup-dir", type=Path, help="Backup directory to restore from.")
    parser.add_argument(
        "--elevate",
        action="store_true",
        help="Relaunch this command as Administrator, then exit this process.",
    )
    parser.add_argument(
        "--no-elevate",
        action="store_true",
        help="Do not auto-elevate when the install directory is not writable.",
    )
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print("ERROR: this patcher only runs on Windows.", file=sys.stderr)
        return 2

    install_dir = args.install_dir or find_install_dir()
    if install_dir is None:
        print("ERROR: Could not auto-detect the install directory.", file=sys.stderr)
        print("Pass --install-dir \"C:\\Program Files\\7-Zip-Zstandard\".", file=sys.stderr)
        return 2
    install_dir = install_dir.resolve()

    if not looks_like_install_dir(install_dir):
        print(f"ERROR: {install_dir} does not look like a 7-Zip install directory.", file=sys.stderr)
        return 2

    if _should_elevate(args, install_dir):
        return _relaunch_as_admin()

    if args.restore:
        backup_dir = args.backup_dir
        if backup_dir is None:
            from .patcher import latest_backup_dir

            backup_dir = latest_backup_dir(install_dir)
        if backup_dir is None:
            print(f"ERROR: no backup directories found in {install_dir}", file=sys.stderr)
            return 1
        if not args.no_kill_locks:
            restore_targets = _restore_targets(install_dir, backup_dir)
            _close_locks(restore_targets, args)
        try:
            restored = restore_backup(install_dir, backup_dir)
        except OSError as exc:
            print(f"ERROR: restore failed: {exc}", file=sys.stderr)
            return 1
        print(f"Restored {len(restored)} file(s).")
        if not args.no_refresh:
            refresh_shell_icons()
        return 0

    if not args.icon.exists():
        print(f"ERROR: icon file not found: {args.icon}", file=sys.stderr)
        return 2

    try:
        icon = IcoFile.from_path(args.icon)
    except Exception as exc:
        print(f"ERROR: could not read ICO: {exc}", file=sys.stderr)
        return 2

    targets = find_patch_targets(install_dir, args.target)
    try:
        plans = build_patch_plans(targets)
    except OSError as exc:
        print(f"ERROR: target inspection failed: {exc}", file=sys.stderr)
        return 1

    print(f"Install directory: {install_dir}")
    print(f"Icon:              {args.icon.resolve()}")
    print(f"Icon images:       {len(icon.images)}")
    print(f"Targets scanned:   {len(targets)}")
    print(f"Targets to patch:  {len(plans)}")

    for plan in plans:
        group_count = sum(len(group.languages) for group in plan.groups)
        print(f"  {plan.path.relative_to(install_dir)}: {group_count} icon group(s)")

    if args.dry_run:
        _print_locks([plan.path for plan in plans])
        print("Dry run only; no files were changed.")
        return 0

    if not plans:
        print("No icon resources found to patch.")
        return 0

    backup_dir = None
    if not args.no_backup:
        backup_dir = make_backup_dir(install_dir)
        try:
            backup_files(plans, install_dir, backup_dir)
        except OSError as exc:
            print(f"ERROR: backup failed: {exc}", file=sys.stderr)
            print("Run as Administrator if the install is under Program Files.", file=sys.stderr)
            return 1
        print(f"Backed up files to: {backup_dir}")

    if not args.no_kill_locks:
        _close_locks([plan.path for plan in plans], args)

    patched_groups = 0
    for plan in plans:
        try:
            patched_groups += patch_file(plan, icon)
        except OSError as exc:
            print(f"ERROR: patch failed for {plan.path}: {exc}", file=sys.stderr)
            print("Close 7-Zip and Explorer windows, or run as Administrator, then retry.", file=sys.stderr)
            if backup_dir:
                print(f"Backups are available at: {backup_dir}", file=sys.stderr)
            return 1

    print(f"Patched {patched_groups} icon group(s) across {len(plans)} file(s).")

    if not args.no_refresh:
        refresh_shell_icons()
        print("Requested Explorer icon cache refresh.")

    return 0


def _default_icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "7zip-box.ico"


def _should_elevate(args: argparse.Namespace, install_dir: Path) -> bool:
    if args.no_elevate or args.dry_run or is_admin():
        return False
    if args.elevate:
        return True
    return not _can_write_directory(install_dir)


def _can_write_directory(path: Path) -> bool:
    marker = path / ".iconpatcher-write-test.tmp"
    try:
        with marker.open("xb") as file:
            file.write(b"")
        marker.unlink()
        return True
    except OSError:
        try:
            marker.unlink()
        except OSError:
            pass
        return False


def _print_locks(paths: list[Path]) -> None:
    try:
        processes = get_locking_processes(paths)
    except OSError as exc:
        print(f"Lock check failed: {exc}")
        return
    if not processes:
        print("Locking processes: none")
        return
    print("Locking processes:")
    for process in processes:
        print(f"  PID {process.pid}: {process.app_name or process.service_name or 'unknown'}")


def _close_locks(paths: list[Path], args: argparse.Namespace) -> None:
    try:
        processes = close_locking_processes(
            paths,
            force=True,
            restart_explorer=not args.no_restart_explorer,
        )
    except OSError as exc:
        print(f"Warning: could not close locking processes: {exc}")
        return
    if not processes:
        return
    print("Closed locking processes:")
    for process in processes:
        print(f"  PID {process.pid}: {process.app_name or process.service_name or 'unknown'}")


def _restore_targets(install_dir: Path, backup_dir: Path) -> list[Path]:
    targets: list[Path] = []
    for source in backup_dir.rglob("*"):
        if source.is_file():
            targets.append(install_dir / source.relative_to(backup_dir))
    return targets


def _relaunch_as_admin() -> int:
    import ctypes

    project_root = Path(__file__).resolve().parent.parent
    params = subprocess.list2cmdline(["-m", "7zip_zstd_iconpatcher", *sys.argv[1:]])
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


if __name__ == "__main__":
    raise SystemExit(main())
