#!/usr/bin/env python3
"""
Windows File Association Setter

This script reads a configuration file containing:
- Line 1: Path to the executable to associate with file types
- Lines 2+: File extensions (one per line, with or without leading dot)

Behavior:
- If an extension has NO existing default app: Sets the specified app as default
- If an extension ALREADY has a default app: Adds the specified app to "Open with" list

Usage:
    python set_file_associations.py <config_file>

Example config file (associations.txt):
    C:\\Program Files\\Notepad++\\notepad++.exe
    .txt
    .log
    .ini
    .cfg
"""

import argparse
import ctypes
import os
import sys
import winreg
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class AssociationInfo:
    """Information about an existing file association."""
    extension: str
    has_default: bool
    progid: Optional[str] = None
    executable: Optional[str] = None
    description: Optional[str] = None


def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_existing_association(extension: str) -> AssociationInfo:
    """
    Check if an extension already has a default application associated.
    
    Args:
        extension: File extension (with leading dot, e.g., '.txt')
        
    Returns:
        AssociationInfo with details about existing association
    """
    info = AssociationInfo(extension=extension, has_default=False)
    
    # First, check UserChoice (Windows 8+ preferred location) - most reliable
    try:
        user_choice_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{extension}\\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, user_choice_path) as key:
            progid, _ = winreg.QueryValueEx(key, "ProgId")
            if progid:
                info.progid = progid
                info.has_default = True
    except (FileNotFoundError, PermissionError, OSError):
        pass
    
    # If no UserChoice, check HKEY_CLASSES_ROOT for the extension
    if not info.has_default:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, extension) as key:
                try:
                    progid, _ = winreg.QueryValueEx(key, "")
                    if progid:
                        info.progid = progid
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            # Extension not registered at all
            return info
    
    # If we found a ProgID, check if it has a valid shell command
    if info.progid:
        try:
            command_path = f"{info.progid}\\shell\\open\\command"
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, command_path) as key:
                command, _ = winreg.QueryValueEx(key, "")
                if command:
                    # Extract executable path from command
                    # Commands are typically: "C:\path\to\app.exe" "%1"
                    if command.startswith('"'):
                        exe_end = command.find('"', 1)
                        if exe_end > 0:
                            info.executable = command[1:exe_end]
                    else:
                        # No quotes, take first space-delimited part
                        parts = command.split()
                        if parts:
                            info.executable = parts[0]
                    
                    # Verify the executable exists (or mark as valid if it's a system app)
                    if info.executable:
                        if os.path.isfile(info.executable):
                            info.has_default = True
                        elif info.progid and not info.executable.startswith('%'):
                            # Could be a system handler, still count as having default
                            info.has_default = True
        except FileNotFoundError:
            pass
        except Exception:
            pass
    
    # Get description if available
    if info.progid:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, info.progid) as key:
                desc, _ = winreg.QueryValueEx(key, "")
                info.description = desc
        except (FileNotFoundError, PermissionError, OSError):
            pass
    
    return info


def create_progid(exe_path: str, progid: str, description: str = None):
    """
    Create or update a ProgID in the registry.
    
    Args:
        exe_path: Full path to the executable
        progid: The programmatic identifier (e.g., 'MyApp.txt')
        description: Optional description for the file type
    """
    exe_path = os.path.abspath(exe_path)
    
    if description is None:
        app_name = Path(exe_path).stem
        description = f"{app_name} Document"
    
    # Create the ProgID key under HKEY_CLASSES_ROOT
    try:
        # Create main ProgID key
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, progid, 0, 
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, description)
        
        # Create DefaultIcon subkey
        icon_path = f'"{exe_path}",0'
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{progid}\\DefaultIcon", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon_path)
        
        # Create shell\open\command subkey
        command = f'"{exe_path}" "%1"'
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{progid}\\shell\\open\\command", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        
        return True
        
    except PermissionError:
        print(f"    [ERROR] Permission denied creating ProgID: {progid}")
        print("            Try running as Administrator.")
        return False
    except Exception as e:
        print(f"    [ERROR] Failed to create ProgID {progid}: {e}")
        return False


def set_extension_association(extension: str, progid: str):
    """
    Associate a file extension with a ProgID (sets as default).
    
    Args:
        extension: File extension (with leading dot, e.g., '.txt')
        progid: The programmatic identifier to associate with
    """
    try:
        # Set the extension to point to our ProgID
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, extension, 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, progid)
        
        return True
        
    except PermissionError:
        print(f"    [ERROR] Permission denied for extension: {extension}")
        return False
    except Exception as e:
        print(f"    [ERROR] Failed to associate {extension}: {e}")
        return False


def add_to_open_with_list(extension: str, progid: str, exe_path: str):
    """
    Add an application to the "Open with" list for an extension.
    This does NOT change the default, just adds it as an option.
    
    Args:
        extension: File extension (with leading dot)
        progid: The programmatic identifier for our app
        exe_path: Path to the executable
    """
    exe_path = os.path.abspath(exe_path)
    exe_name = Path(exe_path).name
    app_name = Path(exe_path).stem
    success = False
    
    # Method 1: Add to OpenWithProgids under the extension in HKCR
    try:
        openwith_path = f"{extension}\\OpenWithProgids"
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, openwith_path, 0,
                                winreg.KEY_WRITE) as key:
            # Value name is the ProgID, value is empty
            winreg.SetValueEx(key, progid, 0, winreg.REG_NONE, b'')
        success = True
    except PermissionError:
        pass
    except Exception:
        pass
    
    # Method 2: Add to user's FileExts OpenWithProgids
    try:
        user_openwith_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{extension}\\OpenWithProgids"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, user_openwith_path, 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, progid, 0, winreg.REG_NONE, b'')
        success = True
    except Exception:
        pass
    
    # Method 3: Register in Applications key (makes it available system-wide for "Open with")
    try:
        app_key_path = f"Applications\\{exe_name}"
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, app_key_path, 0,
                                winreg.KEY_WRITE) as key:
            # Set FriendlyAppName
            winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, app_name)
        
        # Add shell\open\command
        command = f'"{exe_path}" "%1"'
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{app_key_path}\\shell\\open\\command", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        
        # Add SupportedTypes - this is key for "Open with" visibility
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{app_key_path}\\SupportedTypes", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, extension, 0, winreg.REG_SZ, "")
        
        success = True
    except PermissionError:
        pass
    except Exception:
        pass
    
    # Method 4: Add to user's OpenWithList (MRU-based)
    try:
        user_openwith_list = f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{extension}\\OpenWithList"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, user_openwith_list, 0,
                                winreg.KEY_READ | winreg.KEY_WRITE) as key:
            # Find existing apps and MRU list
            existing_apps = {}
            mru_list = ""
            try:
                i = 0
                while True:
                    name, value, _ = winreg.EnumValue(key, i)
                    if name == "MRUList":
                        mru_list = value
                    elif len(name) == 1 and name.isalpha():
                        existing_apps[name] = value.lower()
                    i += 1
            except OSError:
                pass
            
            # Check if our exe is already in the list
            exe_name_lower = exe_name.lower()
            already_exists = exe_name_lower in existing_apps.values()
            
            if not already_exists:
                # Find next available letter
                next_letter = None
                for letter in 'abcdefghijklmnopqrstuvwxyz':
                    if letter not in existing_apps:
                        next_letter = letter
                        break
                
                if next_letter:
                    winreg.SetValueEx(key, next_letter, 0, winreg.REG_SZ, exe_name)
                    # Update MRUList to include our new entry at the front
                    if next_letter not in mru_list:
                        new_mru = next_letter + mru_list
                        winreg.SetValueEx(key, "MRUList", 0, winreg.REG_SZ, new_mru)
                    success = True
    except Exception:
        pass
    
    return success


def register_application(exe_path: str):
    """
    Register the application in Windows App Paths.
    
    Args:
        exe_path: Full path to the executable
    """
    exe_path = os.path.abspath(exe_path)
    exe_name = Path(exe_path).name
    
    # Try HKLM first (system-wide, needs admin)
    try:
        app_paths_key = f"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}"
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, app_paths_key, 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, exe_path)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, str(Path(exe_path).parent))
        
        print(f"  [OK] Registered application in App Paths (system): {exe_name}")
        return True
        
    except PermissionError:
        # Try HKEY_CURRENT_USER instead (user-level, no admin needed)
        try:
            app_paths_key = f"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, app_paths_key, 0,
                                    winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, exe_path)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, str(Path(exe_path).parent))
            print(f"  [OK] Registered application in App Paths (user): {exe_name}")
            return True
        except Exception:
            print(f"  [WARN] Could not register in App Paths")
            return False
    except Exception as e:
        print(f"  [WARN] Failed to register application: {e}")
        return False


def register_in_applications(exe_path: str):
    """
    Register the application in HKCR\\Applications for "Open with" dialogs.
    
    Args:
        exe_path: Full path to the executable
    """
    exe_path = os.path.abspath(exe_path)
    exe_name = Path(exe_path).name
    app_name = Path(exe_path).stem
    
    try:
        app_key_path = f"Applications\\{exe_name}"
        
        # Create main application key
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, app_key_path, 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, app_name)
        
        # Create shell\open\command
        command = f'"{exe_path}" "%1"'
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{app_key_path}\\shell\\open\\command", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        
        # Create DefaultIcon
        icon_path = f'"{exe_path}",0'
        with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, f"{app_key_path}\\DefaultIcon", 0,
                                winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon_path)
        
        print(f"  [OK] Registered in Applications: {exe_name}")
        return True
        
    except PermissionError:
        print(f"  [WARN] Could not register in Applications (needs admin)")
        return False
    except Exception as e:
        print(f"  [WARN] Failed to register in Applications: {e}")
        return False


def notify_shell_change():
    """Notify Windows Shell that file associations have changed."""
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
        print("\n[OK] Notified Windows Shell of association changes")
    except Exception as e:
        print(f"\n[WARN] Could not notify shell: {e}")


def parse_config_file(config_path: str) -> tuple[str, list[str]]:
    """
    Parse the configuration file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Tuple of (exe_path, list_of_extensions)
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]
    
    # Filter out empty lines and comments
    lines = [line for line in lines if line and not line.startswith('#')]
    
    if len(lines) < 2:
        raise ValueError("Config file must contain at least an executable path and one extension")
    
    exe_path = lines[0]
    extensions = []
    
    for ext in lines[1:]:
        # Normalize extension to have leading dot
        if not ext.startswith('.'):
            ext = '.' + ext
        extensions.append(ext.lower())
    
    return exe_path, extensions


def generate_progid(exe_path: str, extension: str) -> str:
    """
    Generate a ProgID for an extension based on the application.
    
    Args:
        exe_path: Path to the executable
        extension: File extension (with dot)
        
    Returns:
        A ProgID string like 'NotepadPlusPlus.txt'
    """
    app_name = Path(exe_path).stem
    # Remove dot and create ProgID
    ext_clean = extension.lstrip('.')
    # Sanitize app name (remove spaces and special chars, keep alphanumeric)
    app_name_clean = ''.join(c for c in app_name if c.isalnum())
    return f"{app_name_clean}.{ext_clean}"


def main():
    parser = argparse.ArgumentParser(
        description="Set Windows default file associations from a configuration file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration file format:
  Line 1: Full path to the executable
  Line 2+: File extensions (one per line, with or without leading dot)
  
  Lines starting with # are treated as comments.

Example config file:
  C:\\Program Files\\Notepad++\\notepad++.exe
  .txt
  .log
  .ini
  # This is a comment
  .cfg
  
Behavior:
  - If an extension has NO default app: Sets the specified app as default
  - If an extension ALREADY has a default: Adds app to "Open with" list only
  - Use --force to override existing defaults

Note: This script works best with Administrator privileges.
        """
    )
    parser.add_argument('config_file', help='Path to the configuration file')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force set as default even if one already exists')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show verbose output')
    
    args = parser.parse_args()
    
    # Check platform
    if sys.platform != 'win32':
        print("Error: This script only works on Windows.")
        sys.exit(1)
    
    # Check admin privileges
    admin_mode = is_admin()
    if not admin_mode:
        print("=" * 70)
        print("WARNING: Not running as Administrator!")
        print("Some operations may fail. For best results, run this script")
        print("from an elevated Command Prompt or PowerShell.")
        print("=" * 70)
        print()
    
    # Parse configuration
    try:
        exe_path, extensions = parse_config_file(args.config_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Validate executable path
    exe_path = os.path.abspath(exe_path)
    if not os.path.isfile(exe_path):
        print(f"Error: Executable not found: {exe_path}")
        sys.exit(1)
    
    app_name = Path(exe_path).stem
    
    print(f"Configuration loaded:")
    print(f"  Executable: {exe_path}")
    print(f"  App Name:   {app_name}")
    print(f"  Extensions: {', '.join(extensions)}")
    if args.force:
        print(f"  Mode:       FORCE (will override existing defaults)")
    else:
        print(f"  Mode:       Respect existing defaults")
    print()
    
    # Check existing associations
    print("Checking existing associations...")
    print("-" * 70)
    
    associations = {}
    for ext in extensions:
        info = get_existing_association(ext)
        associations[ext] = info
        
        if info.has_default:
            if info.executable:
                existing_app = Path(info.executable).stem
            else:
                existing_app = info.progid or "Unknown"
            print(f"  {ext:10} -> Default: {existing_app}")
            if args.verbose and info.executable:
                print(f"             Path: {info.executable}")
        else:
            print(f"  {ext:10} -> No default application")
    
    print("-" * 70)
    print()
    
    if args.dry_run:
        print("[DRY RUN] Would perform the following actions:")
        print()
        print(f"1. Register application: {Path(exe_path).name}")
        print()
        for ext in extensions:
            info = associations[ext]
            progid = generate_progid(exe_path, ext)
            if info.has_default and not args.force:
                if info.executable:
                    existing_app = Path(info.executable).stem
                else:
                    existing_app = info.progid or "Unknown"
                print(f"  {ext}: Add to 'Open with' list (keeping default: {existing_app})")
            else:
                if args.force and info.has_default:
                    print(f"  {ext}: OVERRIDE existing default -> Set {app_name} as default")
                else:
                    print(f"  {ext}: Set {app_name} as DEFAULT (no existing default)")
        print()
        print("2. Notify Windows Shell of changes")
        sys.exit(0)
    
    # Register the application globally
    print("Registering application...")
    register_application(exe_path)
    register_in_applications(exe_path)
    print()
    
    # Process each extension
    print("Processing file associations...")
    print("=" * 70)
    
    set_as_default_count = 0
    added_to_openwith_count = 0
    fail_count = 0
    
    for ext in extensions:
        info = associations[ext]
        progid = generate_progid(exe_path, ext)
        description = f"{app_name} {ext.upper()} File"
        
        print(f"\n{ext}:")
        
        # Always create our ProgID first
        if not create_progid(exe_path, progid, description):
            print(f"    [FAILED] Could not create ProgID")
            fail_count += 1
            continue
        else:
            if args.verbose:
                print(f"    [OK] Created ProgID: {progid}")
        
        if info.has_default and not args.force:
            # Extension already has a default - add to "Open with" only
            if info.executable:
                existing_app = Path(info.executable).stem
            else:
                existing_app = info.progid or "Unknown"
            print(f"    [INFO] Keeping existing default: {existing_app}")
            
            if add_to_open_with_list(ext, progid, exe_path):
                print(f"    [OK] Added '{app_name}' to 'Open with' list")
                added_to_openwith_count += 1
            else:
                print(f"    [WARN] Could not add to 'Open with' list (partial success)")
                # Still count as partial success since ProgID was created
                added_to_openwith_count += 1
        else:
            # No default exists (or --force) - set as default
            if args.force and info.has_default:
                if info.executable:
                    existing_app = Path(info.executable).stem
                else:
                    existing_app = info.progid or "Unknown"
                print(f"    [INFO] Overriding existing default: {existing_app}")
            
            if set_extension_association(ext, progid):
                print(f"    [OK] Set '{app_name}' as DEFAULT for {ext}")
                set_as_default_count += 1
                
                # Also add to Open with for good measure
                add_to_open_with_list(ext, progid, exe_path)
            else:
                print(f"    [FAILED] Could not set as default")
                fail_count += 1
    
    # Notify shell of changes
    notify_shell_change()
    
    # Summary
    print()
    print("=" * 70)
    print("Summary:")
    print(f"  Set as default:           {set_as_default_count}")
    print(f"  Added to 'Open with':     {added_to_openwith_count}")
    print(f"  Failed:                   {fail_count}")
    print("=" * 70)
    
    if fail_count > 0 and not admin_mode:
        print()
        print("Tip: Run as Administrator for better results.")
    
    if set_as_default_count > 0 or added_to_openwith_count > 0:
        print()
        print("Changes applied successfully!")
        print()
        print("You may need to restart Explorer or log out/in for all changes")
        print("to take effect.")
        print()
        if added_to_openwith_count > 0:
            print(f"To open files with {app_name}:")
            print("  - Right-click a file -> 'Open with' -> Choose another app")
            print(f"  - Select '{app_name}' from the list")


if __name__ == "__main__":
    main()