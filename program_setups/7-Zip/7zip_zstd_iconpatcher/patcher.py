from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import ctypes
import shutil
import subprocess

from .ico import IcoFile, parse_group_icon_ids
from .winresources import RT_GROUP_ICON, RT_ICON, ResourceModule, ResourceName, ResourceUpdater


DEFAULT_EXTENSIONS = {".exe", ".dll", ".sfx"}
BACKUP_ROOT_NAME = ".iconpatcher-backups"


@dataclass(frozen=True)
class IconGroup:
    name: ResourceName
    languages: tuple[int, ...]


@dataclass(frozen=True)
class PatchPlan:
    path: Path
    groups: tuple[IconGroup, ...]
    existing_icon_ids: frozenset[int]


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def find_patch_targets(install_dir: Path, explicit_targets: list[str] | None = None) -> list[Path]:
    if explicit_targets:
        paths = []
        for target in explicit_targets:
            path = Path(target)
            if not path.is_absolute():
                path = install_dir / path
            paths.append(path)
        return paths

    targets: list[Path] = []
    for path in sorted(install_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in DEFAULT_EXTENSIONS:
            targets.append(path)

    codecs_dir = install_dir / "Codecs"
    if codecs_dir.is_dir():
        for path in sorted(codecs_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in DEFAULT_EXTENSIONS:
                targets.append(path)

    return targets


def inspect_target(path: Path) -> PatchPlan | None:
    if not path.exists():
        raise FileNotFoundError(path)

    with ResourceModule(path) as module:
        group_names = module.enum_names(RT_GROUP_ICON)
        if not group_names:
            return None

        icon_names = module.enum_names(RT_ICON)
        existing_icon_ids = frozenset(name for name in icon_names if isinstance(name, int))

        groups: list[IconGroup] = []
        for name in group_names:
            languages = module.enum_languages(RT_GROUP_ICON, name)
            if not languages:
                languages = [0]
            groups.append(IconGroup(name=name, languages=tuple(languages)))

    return PatchPlan(path=path, groups=tuple(groups), existing_icon_ids=existing_icon_ids)


def build_patch_plans(targets: list[Path]) -> list[PatchPlan]:
    plans: list[PatchPlan] = []
    for target in targets:
        plan = inspect_target(target)
        if plan:
            plans.append(plan)
    return plans


def patch_file(plan: PatchPlan, icon: IcoFile) -> int:
    patched_groups = 0
    next_icon_id = _next_icon_id(plan.existing_icon_ids)

    with ResourceModule(plan.path) as module:
        group_icon_ids: dict[tuple[ResourceName, int], list[int]] = {}
        for group in plan.groups:
            for language in group.languages:
                try:
                    data = module.read(RT_GROUP_ICON, group.name, language)
                    ids = parse_group_icon_ids(data)
                except OSError:
                    ids = []

                if len(ids) < len(icon.images):
                    ids = ids[:]
                    while len(ids) < len(icon.images):
                        ids.append(next_icon_id)
                        next_icon_id += 1
                else:
                    ids = ids[: len(icon.images)]
                group_icon_ids[(group.name, language)] = ids

    with ResourceUpdater(plan.path) as updater:
        for group in plan.groups:
            for language in group.languages:
                ids = group_icon_ids[(group.name, language)]
                for image, icon_id in zip(icon.images, ids):
                    updater.update(RT_ICON, icon_id, language, image.data)
                updater.update(RT_GROUP_ICON, group.name, language, icon.to_group_icon(ids))
                patched_groups += 1
        updater.commit()

    return patched_groups


def make_backup_dir(install_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return install_dir / BACKUP_ROOT_NAME / stamp


def backup_files(plans: list[PatchPlan], install_dir: Path, backup_dir: Path) -> None:
    for plan in plans:
        rel = plan.path.relative_to(install_dir)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan.path, dest)


def latest_backup_dir(install_dir: Path) -> Path | None:
    root = install_dir / BACKUP_ROOT_NAME
    if not root.is_dir():
        return None
    dirs = [path for path in root.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return sorted(dirs)[-1]


def restore_backup(install_dir: Path, backup_dir: Path | None = None) -> list[Path]:
    backup_dir = backup_dir or latest_backup_dir(install_dir)
    if backup_dir is None:
        raise FileNotFoundError(f"no backup directories found in {install_dir / BACKUP_ROOT_NAME}")
    if not backup_dir.is_dir():
        raise FileNotFoundError(backup_dir)

    restored: list[Path] = []
    for source in backup_dir.rglob("*"):
        if source.is_file():
            rel = source.relative_to(backup_dir)
            dest = install_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            restored.append(dest)
    return restored


def refresh_shell_icons() -> None:
    shell32 = ctypes.windll.shell32
    shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    subprocess.run(
        ["ie4uinit.exe", "-show"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _next_icon_id(existing: frozenset[int]) -> int:
    next_id = 1000
    while next_id in existing:
        next_id += 1
    return next_id
