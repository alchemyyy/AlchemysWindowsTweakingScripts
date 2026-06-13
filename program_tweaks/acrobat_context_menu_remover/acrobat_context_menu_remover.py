#!/usr/bin/env python3
r"""
acrobat_context_menu_nuke.py

Aggressively removes Adobe Acrobat Explorer context-menu entries such as:
  - Convert to Adobe PDF
  - Convert and Share with Adobe PDF
  - Convert with Acrobat
  - Edit with Acrobat / Edit with Adobe Acrobat

Use:
  py -3 acrobat_context_menu_nuke.py --scan --deep
  py -3 acrobat_context_menu_nuke.py --apply --deep --quarantine-dlls --kill-acrobat --restart-explorer
  py -3 acrobat_context_menu_nuke.py --restore C:\path\to\backup_YYYYMMDD_HHMMSS.json --restart-explorer

The script creates a JSON backup before modifying registry keys. It targets Acrobat
Explorer context-menu integration, not Acrobat's normal PDF file association.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

if os.name == "nt":
    import winreg  # type: ignore
else:
    winreg = None  # type: ignore

SCRIPT = "acrobat_context_menu_nuke"
GUID_RE = re.compile(r"\{?[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}?")

KNOWN_CLSIDS: Dict[str, str] = {
    "{A6595CD1-BF77-430A-A452-18696685F7C7}": "Adobe Acrobat legacy/Elements context menu",
    "{3282E233-C5D3-4533-9B25-44B8AAAFACFA}": "Adobe Acrobat Windows 11 Convert/Share context menu",
    "{30DEEDF6-63EA-4042-A7D8-0A9E1B17BB99}": "Adobe Acrobat Edit context menu",
}

ACROBAT_TERMS = (
    "acrobat",
    "adobe pdf",
    "pdfmaker",
    "acroexch",
    "acrotray",
    "acrobat elements",
    "adobeacrobatdccoreapp",
    "contextmenushim",
    "contextmenuiexplorercommandshim",
    "contextmenu64.dll",
    "contextmenu.dll",
)

STATIC_MENU_TERMS = (
    "convert to adobe pdf",
    "convert and share",
    "convert with acrobat",
    "convert to pdf",
    "create pdf",
    "share with adobe pdf",
    "combine files",
    "combine in acrobat",
    "edit with adobe acrobat",
    "edit with acrobat",
    "adobe pdf",
)

STANDARD_VERBS = {
    "open", "print", "printto", "properties", "runas", "runasuser",
    "find", "explore", "preview", "opennewwindow", "play",
}

TARGET_DLLS = {
    "contextmenu.dll",
    "contextmenu64.dll",
    "contextmenushim64.dll",
    "contextmenuiexplorercommandshim.dll",
    "acrobatcontextmenu.dll",
}

CLASSES = r"Software\Classes"
BLOCKED = r"Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved"


@dataclass(frozen=True)
class Ref:
    root: str
    path: str
    view_name: str = "default"
    view_flag: int = 0

    def child(self, name: str) -> "Ref":
        return Ref(self.root, self.path + "\\" + name, self.view_name, self.view_flag)

    def ident(self) -> str:
        return f"{self.root}|{self.view_name}|{self.path}"

    def display(self) -> str:
        suffix = "" if self.view_name == "default" else f" [{self.view_name}-bit view]"
        return f"{self.root}\\{self.path}{suffix}"


def fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def is_64bit_os() -> bool:
    return bool(os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("ProgramFiles(x86)") or platform.machine().endswith("64"))


def views() -> List[Tuple[str, int]]:
    if winreg is None:
        return []
    if is_64bit_os():
        return [("64", winreg.KEY_WOW64_64KEY), ("32", winreg.KEY_WOW64_32KEY)]
    return [("default", 0)]


def root_handle(root: str):
    if winreg is None:
        fail("This script only runs on Windows.")
    if root == "HKCU":
        return winreg.HKEY_CURRENT_USER
    if root == "HKLM":
        return winreg.HKEY_LOCAL_MACHINE
    if root == "HKCR":
        return winreg.HKEY_CLASSES_ROOT
    raise ValueError(root)


def open_key(ref: Ref, access: int):
    return winreg.OpenKey(root_handle(ref.root), ref.path, 0, access | ref.view_flag)


def create_key(ref: Ref):
    return winreg.CreateKeyEx(root_handle(ref.root), ref.path, 0, winreg.KEY_READ | winreg.KEY_WRITE | ref.view_flag)


def exists(ref: Ref) -> bool:
    try:
        with open_key(ref, winreg.KEY_READ):
            return True
    except OSError:
        return False


def subkeys(ref: Ref) -> List[str]:
    try:
        with open_key(ref, winreg.KEY_READ) as k:
            return [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]
    except OSError:
        return []


def values(ref: Ref) -> List[Tuple[str, Any, int]]:
    try:
        with open_key(ref, winreg.KEY_READ) as k:
            return [winreg.EnumValue(k, i) for i in range(winreg.QueryInfoKey(k)[1])]
    except OSError:
        return []


def default_value(ref: Ref) -> Optional[Tuple[Any, int]]:
    try:
        with open_key(ref, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, "")
    except OSError:
        return None


def enc(data: Any) -> Any:
    if isinstance(data, bytes):
        return {"__bytes_b64__": base64.b64encode(data).decode("ascii")}
    return data


def dec(data: Any) -> Any:
    if isinstance(data, dict) and "__bytes_b64__" in data:
        return base64.b64decode(data["__bytes_b64__"])
    return data


def read_tree(ref: Ref, depth: int = 0, max_depth: int = 64) -> Optional[Dict[str, Any]]:
    try:
        with open_key(ref, winreg.KEY_READ) as k:
            nsub, nval, _ = winreg.QueryInfoKey(k)
            vals: Dict[str, Dict[str, Any]] = {}
            for i in range(nval):
                name, data, typ = winreg.EnumValue(k, i)
                vals[name] = {"type": typ, "data": enc(data)}
            kids: Dict[str, Any] = {}
            if depth < max_depth:
                for i in range(nsub):
                    name = winreg.EnumKey(k, i)
                    kids[name] = read_tree(ref.child(name), depth + 1, max_depth)
            return {"values": vals, "subkeys": kids}
    except OSError:
        return None


def write_tree(ref: Ref, state: Dict[str, Any]) -> None:
    with create_key(ref) as k:
        for name, info in state.get("values", {}).items():
            winreg.SetValueEx(k, name, 0, int(info["type"]), dec(info["data"]))
    for name, child_state in state.get("subkeys", {}).items():
        if child_state is not None:
            write_tree(ref.child(name), child_state)


def delete_tree(ref: Ref) -> None:
    for name in subkeys(ref):
        delete_tree(ref.child(name))
    try:
        winreg.DeleteKeyEx(root_handle(ref.root), ref.path, ref.view_flag, 0)
    except AttributeError:
        winreg.DeleteKey(root_handle(ref.root), ref.path)
    except OSError:
        winreg.DeleteKey(root_handle(ref.root), ref.path)


def restore_ref(ref: Ref, state: Optional[Dict[str, Any]]) -> None:
    if exists(ref):
        delete_tree(ref)
    if state is not None:
        write_tree(ref, state)


def normalize_guid(s: str) -> Optional[str]:
    m = GUID_RE.search(s or "")
    if not m:
        return None
    g = m.group(0).upper()
    if not g.startswith("{"):
        g = "{" + g + "}"
    return g


def guids_in(s: str) -> Set[str]:
    out: Set[str] = set()
    for m in GUID_RE.finditer(s or ""):
        g = normalize_guid(m.group(0))
        if g:
            out.add(g)
    return out


def has_acrobat(s: str, all_adobe: bool = False) -> bool:
    t = (s or "").lower()
    return any(x in t for x in ACROBAT_TERMS) or (all_adobe and "adobe" in t)


def has_static_label(s: str) -> bool:
    t = (s or "").lower()
    return any(x in t for x in STATIC_MENU_TERMS)


def key_text(ref: Ref, max_depth: int = 3, max_chars: int = 20000) -> str:
    parts: List[str] = [ref.path]

    def visit(r: Ref, depth: int) -> None:
        if sum(len(x) for x in parts) > max_chars:
            return
        for n, d, typ in values(r):
            parts.extend([str(n), str(d), str(typ)])
        if depth >= max_depth:
            return
        for child in subkeys(r):
            parts.append(child)
            visit(r.child(child), depth + 1)

    visit(ref, 0)
    return "\n".join(parts)[:max_chars]


def cls_ref(root: str, rel: str, view: Tuple[str, int]) -> Ref:
    return Ref(root, CLASSES + ("\\" + rel if rel else ""), view[0], view[1])


def clsid_text(guid: str, vws: Sequence[Tuple[str, int]]) -> str:
    chunks = [guid]
    for root in ("HKCU", "HKLM"):
        for vw in vws:
            for rel in (rf"CLSID\{guid}", rf"WOW6432Node\CLSID\{guid}", rf"PackagedCom\ClassIndex\{guid}"):
                r = cls_ref(root, rel, vw)
                if exists(r):
                    chunks.append(r.display())
                    chunks.append(key_text(r, 4, 12000))
    return "\n".join(chunks)


def walk(base: Ref, max_keys: int, skip_huge: bool = True) -> Iterable[Ref]:
    stack = [base]
    seen = 0
    while stack:
        r = stack.pop()
        seen += 1
        if seen > max_keys:
            print(f"WARNING: hit --max-keys={max_keys}; scan may be incomplete.")
            return
        yield r
        low = r.path.lower()
        if skip_huge and (low.endswith(r"software\classes\clsid") or low.endswith(r"software\classes\wow6432node\clsid") or low.endswith(r"software\classes\interface") or low.endswith(r"software\classes\typelib")):
            continue
        for name in reversed(subkeys(r)):
            stack.append(r.child(name))


def action_key(a: Dict[str, Any]) -> Tuple[Any, ...]:
    return (a["kind"], a["ref"].ident(), a.get("name"), str(a.get("data")))


def add(actions: List[Dict[str, Any]], seen: Set[Tuple[Any, ...]], a: Dict[str, Any]) -> None:
    k = action_key(a)
    if k not in seen:
        actions.append(a)
        seen.add(k)


def add_block(actions: List[Dict[str, Any]], seen: Set[Tuple[Any, ...]], clsids: Iterable[str], vws: Sequence[Tuple[str, int]]) -> None:
    for guid in sorted(set(clsids)):
        label = KNOWN_CLSIDS.get(guid, "Discovered Acrobat context-menu handler")
        for root in ("HKCU", "HKLM"):
            for vw in vws:
                add(actions, seen, {"kind": "set", "ref": Ref(root, BLOCKED, vw[0], vw[1]), "name": guid, "type": winreg.REG_SZ, "data": label, "why": f"Block {guid} ({label})"})


def should_handler(ref: Ref, name: str, vws: Sequence[Tuple[str, int]], all_adobe: bool) -> Tuple[bool, Set[str], str]:
    dv = default_value(ref)
    dtext = str(dv[0]) if dv else ""
    found = guids_in(name + "\n" + dtext)
    text = name + "\n" + dtext + "\n" + key_text(ref, 2)
    for g in list(found):
        text += "\n" + clsid_text(g, vws)
    if found & set(KNOWN_CLSIDS):
        return True, found, "known Acrobat CLSID"
    if has_acrobat(text, all_adobe):
        return True, found, "handler name/value/CLSID mentions Acrobat"
    return False, found, ""


def should_static_verb(ref: Ref, verb: str, all_adobe: bool) -> Tuple[bool, str]:
    if verb.lower() in STANDARD_VERBS:
        return False, "standard verb skipped"
    text = verb + "\n" + key_text(ref, 4)
    if has_acrobat(text, all_adobe) and has_static_label(text):
        return True, "Acrobat Convert/Share/Edit static shell verb"
    return False, ""


def build_actions(deep: bool, all_adobe: bool, max_keys: int) -> Tuple[List[Dict[str, Any]], Set[str]]:
    vws = views()
    actions: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, ...]] = set()
    discovered: Set[str] = set(KNOWN_CLSIDS)

    add_block(actions, seen, discovered, vws)

    # Remove Approved whitelist values for Acrobat CLSIDs/labels.
    for root in ("HKCU", "HKLM"):
        for vw in vws:
            r = Ref(root, APPROVED, vw[0], vw[1])
            for n, d, _ in values(r):
                g = normalize_guid(n)
                if (g and g in discovered) or has_acrobat(f"{n}\n{d}", all_adobe):
                    add(actions, seen, {"kind": "delvalue", "ref": r, "name": n, "why": f"Remove Acrobat value from Shell Extensions\\Approved: {n}"})

    # Delete known context-menu COM registrations.
    for guid, label in KNOWN_CLSIDS.items():
        for root in ("HKCU", "HKLM"):
            for vw in vws:
                for rel in (rf"CLSID\{guid}", rf"WOW6432Node\CLSID\{guid}", rf"PackagedCom\ClassIndex\{guid}"):
                    r = cls_ref(root, rel, vw)
                    if exists(r):
                        add(actions, seen, {"kind": "delkey", "ref": r, "why": f"Delete known Acrobat context-menu CLSID registration: {guid} ({label})"})

    # Scan context menu handlers and safe static verbs.
    for root in ("HKCU", "HKLM"):
        for vw in vws:
            base = Ref(root, CLASSES, vw[0], vw[1])
            if not exists(base):
                continue
            if deep:
                containers = [r for r in walk(base, max_keys=max_keys) if r.path.lower().endswith(r"\shellex\contextmenuhandlers") or r.path.lower().endswith(r"\shell")]
            else:
                common = [
                    r"*\shellex\ContextMenuHandlers",
                    r"AllFilesystemObjects\shellex\ContextMenuHandlers",
                    r"Directory\shellex\ContextMenuHandlers",
                    r"Directory\Background\shellex\ContextMenuHandlers",
                    r"Folder\shellex\ContextMenuHandlers",
                    r"Drive\shellex\ContextMenuHandlers",
                ]
                containers = [cls_ref(root, rel, vw) for rel in common]

            for c in containers:
                low = c.path.lower()
                if low.endswith(r"\shellex\contextmenuhandlers"):
                    for h in subkeys(c):
                        hr = c.child(h)
                        target, gs, why = should_handler(hr, h, vws, all_adobe)
                        if target:
                            discovered |= gs
                            for g in gs:
                                add(actions, seen, {"kind": "set", "ref": hr, "name": "", "type": winreg.REG_SZ, "data": "--" + g, "why": f"Poison handler default before deletion ({why})"})
                            add(actions, seen, {"kind": "delkey", "ref": hr, "why": f"Delete Acrobat ContextMenuHandler ({why})"})
                elif low.endswith(r"\shell"):
                    if "\\classes\\clsid\\" in low or "\\classes\\wow6432node\\clsid\\" in low:
                        continue
                    for verb in subkeys(c):
                        vr = c.child(verb)
                        target, why = should_static_verb(vr, verb, all_adobe)
                        if target:
                            discovered |= guids_in(key_text(vr, 4))
                            add(actions, seen, {"kind": "delkey", "ref": vr, "why": f"Delete Acrobat static shell verb ({why})"})

            # Windows 11 packaged handlers can expose CLSIDs under PackagedCom.
            packaged = cls_ref(root, "PackagedCom", vw)
            if exists(packaged):
                for r in walk(packaged, max_keys=min(max_keys, 40000), skip_huge=False):
                    txt = r.path + "\n" + key_text(r, 1, 8000)
                    if has_acrobat(txt, all_adobe):
                        discovered |= guids_in(txt)

    # Block and remove registrations for any newly discovered Acrobat CLSIDs.
    add_block(actions, seen, discovered, vws)
    for guid in sorted(discovered):
        info = clsid_text(guid, vws)
        if guid in KNOWN_CLSIDS or has_acrobat(info, all_adobe):
            for root in ("HKCU", "HKLM"):
                for vw in vws:
                    for rel in (rf"CLSID\{guid}", rf"WOW6432Node\CLSID\{guid}", rf"PackagedCom\ClassIndex\{guid}"):
                        r = cls_ref(root, rel, vw)
                        if exists(r):
                            add(actions, seen, {"kind": "delkey", "ref": r, "why": f"Delete discovered Acrobat context-menu CLSID registration: {guid}"})

    def sort_key(a: Dict[str, Any]) -> Tuple[int, int]:
        order = {"set": 0, "delvalue": 1, "delkey": 2}[a["kind"]]
        depth = a["ref"].path.count("\\")
        return (order, -depth if a["kind"] == "delkey" else depth)

    actions.sort(key=sort_key)
    return actions, discovered


def backup_ref(backup: Dict[str, Any], ref: Ref) -> None:
    pre = backup.setdefault("registry_preimages", {})
    if ref.ident() not in pre:
        pre[ref.ident()] = {"root": ref.root, "path": ref.path, "view_name": ref.view_name, "view_flag": ref.view_flag, "state": read_tree(ref)}


def apply_actions(actions: Sequence[Dict[str, Any]], backup: Dict[str, Any]) -> Tuple[int, List[str]]:
    errors: List[str] = []
    done = 0
    for a in actions:
        r: Ref = a["ref"]
        try:
            if a["kind"] == "set":
                backup_ref(backup, r)
                with create_key(r) as k:
                    winreg.SetValueEx(k, a["name"], 0, int(a["type"]), a["data"])
                done += 1
            elif a["kind"] == "delvalue":
                backup_ref(backup, r)
                try:
                    with open_key(r, winreg.KEY_SET_VALUE | winreg.KEY_READ) as k:
                        winreg.DeleteValue(k, a["name"])
                    done += 1
                except FileNotFoundError:
                    pass
            elif a["kind"] == "delkey":
                if exists(r):
                    backup_ref(backup, r)
                    delete_tree(r)
                    done += 1
        except Exception as e:  # keep going
            errors.append(f"FAILED {a['kind']} {r.display()}: {e}")
    return done, errors


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_if_needed(args: argparse.Namespace) -> None:
    if os.name != "nt" or args.scan or args.no_elevate or is_admin():
        return
    params = subprocess.list2cmdline([str(Path(__file__).resolve())] + sys.argv[1:] + ["--no-elevate"])
    print("Requesting administrator privileges...")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if rc <= 32:
        fail(f"Elevation failed with ShellExecuteW return code {rc}. Run from an elevated terminal.")
    raise SystemExit(0)


def notify_shell() -> None:
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def restart_explorer() -> None:
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.Popen(["explorer.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill_acrobat() -> None:
    for p in ["Acrobat.exe", "AcroRd32.exe", "AcroCEF.exe", "RdrCEF.exe", "AcroTray.exe", "acrodist.exe", "AdobeCollabSync.exe"]:
        subprocess.run(["taskkill", "/f", "/im", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def inproc_dlls_for_guid(guid: str, vws: Sequence[Tuple[str, int]]) -> Set[Path]:
    out: Set[Path] = set()
    for root in ("HKCU", "HKLM"):
        for vw in vws:
            for rel in (rf"CLSID\{guid}\InprocServer32", rf"WOW6432Node\CLSID\{guid}\InprocServer32"):
                r = cls_ref(root, rel, vw)
                dv = default_value(r)
                if dv and isinstance(dv[0], str):
                    p = Path(os.path.expandvars(dv[0].strip('"')))
                    if p.name.lower() in TARGET_DLLS:
                        out.add(p)
    return out


def candidate_dlls(discovered: Iterable[str], vws: Sequence[Tuple[str, int]]) -> Set[Path]:
    out: Set[Path] = set()
    for g in discovered:
        out |= inproc_dlls_for_guid(g, vws)
    for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base_s = os.environ.get(env)
        if not base_s:
            continue
        adobe = Path(base_s) / "Adobe"
        if not adobe.exists():
            continue
        for pattern in ("Acrobat*/Acrobat Elements", "Acrobat Reader*/Reader/Acrobat Elements", "Acrobat DC/Acrobat Elements"):
            for d in adobe.glob(pattern):
                if d.is_dir():
                    for name in TARGET_DLLS:
                        p = d / name
                        if p.exists():
                            out.add(p)
        try:
            for d in adobe.rglob("Acrobat Elements"):
                if d.is_dir() and "acrobat" in str(d).lower():
                    for name in TARGET_DLLS:
                        p = d / name
                        if p.exists():
                            out.add(p)
        except OSError:
            pass
    return {p for p in out if p.exists() and p.is_file()}


def quarantine(paths: Iterable[Path], backup: Dict[str, Any]) -> Tuple[int, List[str]]:
    moved = 0
    errors: List[str] = []
    stamp = backup["timestamp_compact"]
    moves = backup.setdefault("file_moves", [])
    for p in sorted(paths):
        try:
            subprocess.run(["regsvr32.exe", "/u", "/s", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            dest = p.with_name(p.name + f".disabled-by-{SCRIPT}-{stamp}")
            n = 1
            while dest.exists():
                dest = p.with_name(p.name + f".disabled-by-{SCRIPT}-{stamp}.{n}")
                n += 1
            p.rename(dest)
            moves.append({"src": str(p), "dest": str(dest)})
            moved += 1
        except Exception as e:
            errors.append(f"FAILED to quarantine {p}: {e}")
    return moved, errors


def save_backup(backup: Dict[str, Any], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"backup_{backup['timestamp_compact']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    return path


def restore(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        backup = json.load(f)
    errors: List[str] = []
    items = sorted(backup.get("registry_preimages", {}).values(), key=lambda x: x["path"].count("\\"), reverse=True)
    restored = 0
    for item in items:
        r = Ref(item["root"], item["path"], item.get("view_name", "default"), int(item.get("view_flag", 0)))
        try:
            restore_ref(r, item.get("state"))
            restored += 1
        except Exception as e:
            errors.append(f"FAILED restore {r.display()}: {e}")
    file_restored = 0
    for move in reversed(backup.get("file_moves", [])):
        src = Path(move["src"])
        dest = Path(move["dest"])
        try:
            if dest.exists() and not src.exists():
                dest.rename(src)
                file_restored += 1
            elif dest.exists() and src.exists():
                errors.append(f"Skipped file restore; original exists: {src}")
        except Exception as e:
            errors.append(f"FAILED restore file {src}: {e}")
    print(f"Restored registry keys/values: {restored}")
    print(f"Restored quarantined files: {file_restored}")
    if errors:
        print("Warnings/errors:")
        for e in errors:
            print("  " + e)


def parse(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Nuke Adobe Acrobat Explorer context-menu entries.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true", help="Scan only; make no changes.")
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    mode.add_argument("--restore", help="Restore using a backup JSON created by this script.")
    p.add_argument("--deep", action="store_true", help="Deep scan Software\\Classes. Recommended.")
    p.add_argument("--all-adobe", action="store_true", help="Broaden matching from Acrobat/PDFMaker to all Adobe entries. More destructive.")
    p.add_argument("--quarantine-dlls", action="store_true", help="Rename Acrobat ContextMenu*.dll files after registry removal.")
    p.add_argument("--kill-acrobat", action="store_true", help="Kill Acrobat/Reader/AcroTray before quarantining DLLs.")
    p.add_argument("--restart-explorer", action="store_true", help="Restart Explorer after changes.")
    p.add_argument("--no-elevate", action="store_true", help="Do not auto-request admin rights.")
    p.add_argument("--max-keys", type=int, default=150000)
    p.add_argument("--backup-dir", default=str(Path.cwd() / "acrobat_context_menu_backups"))
    a = p.parse_args(argv)
    if not (a.scan or a.apply or a.restore):
        a.scan = True
    return a


def main(argv: Sequence[str]) -> int:
    if os.name != "nt" or winreg is None:
        fail("This script only runs on Windows.")
    args = parse(argv)
    elevate_if_needed(args)

    if args.restore:
        restore(Path(args.restore))
        notify_shell()
        if args.restart_explorer:
            restart_explorer()
        return 0

    print(f"Mode: {'APPLY' if args.apply else 'SCAN'}")
    print(f"Admin: {'yes' if is_admin() else 'no'}")
    print(f"Deep scan: {'yes' if args.deep else 'no'}")
    print(f"All Adobe: {'yes' if args.all_adobe else 'no'}")
    print()

    actions, discovered = build_actions(args.deep, args.all_adobe, args.max_keys)
    print(f"Registry actions planned: {len(actions)}")
    for i, a in enumerate(actions[:100], 1):
        r: Ref = a["ref"]
        extra = f" value={a.get('name')!r}" if a["kind"] in ("set", "delvalue") else ""
        print(f"{i:03d}. {a['kind']:8s} {r.display()}{extra}")
        print(f"     {a['why']}")
    if len(actions) > 100:
        print(f"... {len(actions)-100} more actions not shown.")

    vws = views()
    dlls: Set[Path] = set()
    if args.quarantine_dlls:
        dlls = candidate_dlls(discovered, vws)
        print(f"\nContext-menu DLLs planned for quarantine: {len(dlls)}")
        for p in sorted(dlls):
            print(f"  {p}")

    if args.scan:
        print("\nScan only. Re-run with --apply to change anything.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup: Dict[str, Any] = {
        "script": SCRIPT,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "timestamp_compact": stamp,
        "argv": list(argv),
        "registry_preimages": {},
        "file_moves": [],
        "discovered_clsids": sorted(discovered),
    }
    for a in actions:
        backup_ref(backup, a["ref"])
    backup_path = save_backup(backup, Path(args.backup_dir))
    print(f"\nBackup written before changes: {backup_path}")

    if args.kill_acrobat or args.quarantine_dlls:
        kill_acrobat()
    done, errors = apply_actions(actions, backup)
    moved = 0
    file_errors: List[str] = []
    if args.quarantine_dlls:
        moved, file_errors = quarantine(dlls, backup)
    backup_path = save_backup(backup, Path(args.backup_dir))
    notify_shell()
    if args.restart_explorer:
        restart_explorer()

    print(f"\nApplied registry changes: {done}")
    print(f"Quarantined DLLs: {moved}")
    print(f"Final backup: {backup_path}")
    print("Restore command:")
    print(f"  py -3 {Path(__file__).name} --restore \"{backup_path}\" --restart-explorer")

    all_errors = errors + file_errors
    if all_errors:
        print("\nWarnings/errors:")
        for e in all_errors:
            print("  " + e)
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
