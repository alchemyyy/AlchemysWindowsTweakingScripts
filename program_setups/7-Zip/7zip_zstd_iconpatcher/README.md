# 7-Zip Zstandard Icon Patcher

Python patcher for an installed 7-Zip Zstandard instance. It replaces icon
resources inside installed `.exe`, `.dll`, and `.sfx` files with a supplied
ICO, without rebuilding 7-Zip and without changing source code.

The default bundled icon is `assets/7zip-box.ico`.

## Usage

Run from the parent `7zip_zstd_alchemys_preferred_setup` directory:

```bat
run_7zip_zstd_iconpatcher.cmd
```

Or call Python directly:

```bat
python -m 7zip_zstd_iconpatcher --install-dir "C:\Program Files\7-Zip-Zstandard"
```

Auto-detect the install directory:

```bat
python -m 7zip_zstd_iconpatcher
```

Dry run:

```bat
python -m 7zip_zstd_iconpatcher --dry-run
```

Use a different ICO:

```bat
python -m 7zip_zstd_iconpatcher --icon "C:\path\custom.ico"
```

Restore the latest backup:

```bat
python -m 7zip_zstd_iconpatcher --restore
```

## Automatic Handling

For normal patch runs, the patcher tries to make the operation complete without
manual cleanup:

- auto-elevates when the install directory is not writable
- asks Windows Restart Manager which processes are locking target files
- gracefully closes lockers, then force-kills any remaining lockers
- restarts Explorer if Explorer had to be closed
- refreshes shell icons after patching

Opt out if needed:

```bat
python -m 7zip_zstd_iconpatcher --no-kill-locks
python -m 7zip_zstd_iconpatcher --no-elevate
python -m 7zip_zstd_iconpatcher --no-restart-explorer
```

## What It Patches

By default, it scans the install directory plus `Codecs\` for files ending in:

- `.exe`
- `.dll`
- `.sfx`

For each file with `RT_GROUP_ICON` resources, it replaces every icon group with
the selected ICO. This handles:

- titlebar and taskbar icons
- GUI dialog icons
- shell extension icons
- file association icons that point at existing resource indexes

Registry file associations are not rewritten. They keep pointing at the same
installed binary and resource index; the resource at that index is replaced.

## Notes

- Close unsaved work in apps that might be using 7-Zip before patching. Locking
  processes can be closed or force-killed.
- The patcher creates timestamped backups under `.iconpatcher-backups`.
- Authenticode signatures are not preserved. This project intentionally ignores
  signing.
